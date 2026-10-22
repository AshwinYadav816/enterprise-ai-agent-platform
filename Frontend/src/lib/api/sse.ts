import { EventStreamContentType, fetchEventSource } from "@microsoft/fetch-event-source";

import { API_BASE, getToken, handleAuthLost, refreshAccessToken } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";
import type {
  AgentData,
  DoneData,
  ErrorData,
  ResultData,
  SendMessageBody,
  Source,
  StatusData,
} from "@/lib/chat/types";

export type StreamHandlers = {
  /** The server accepted the message (the user message is saved from here on). */
  onOpen?: () => void;
  onStatus?: (data: StatusData) => void;
  onAgent?: (data: AgentData) => void;
  onSources?: (sources: Source[]) => void;
  onToken?: (text: string) => void;
  onResult?: (data: ResultData) => void;
  /** A step failed; user-safe message. The stream continues. */
  onError?: (data: ErrorData) => void;
  onDone?: (data: DoneData) => void;
};

export type StreamOutcome = { done: boolean };

class NeedsRefresh extends Error {}

/**
 * POST a chat message and dispatch the SSE reply by event name. Resolves when the stream ends
 * (`done: false` if it was aborted or closed early). Rejects with ApiError when the server refuses
 * the message (429, 404, 409, 422…). Never retries on its own — a retried POST would send the
 * message twice — except once after a 401, with a refreshed token (nothing was saved then).
 */
export async function streamMessage(
  conversationId: string,
  body: SendMessageBody,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<StreamOutcome> {
  try {
    return await attempt(conversationId, body, handlers, signal);
  } catch (error) {
    if (!(error instanceof NeedsRefresh)) throw error;
  }
  const session = await refreshAccessToken();
  if (!session) {
    handleAuthLost();
    throw new ApiError(401, "unauthorized", "Your session has expired. Please sign in again.");
  }
  try {
    return await attempt(conversationId, body, handlers, signal);
  } catch (error) {
    if (error instanceof NeedsRefresh) {
      handleAuthLost();
      throw new ApiError(401, "unauthorized", "Your session has expired. Please sign in again.");
    }
    throw error;
  }
}

async function attempt(
  conversationId: string,
  body: SendMessageBody,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<StreamOutcome> {
  let done = false;
  const token = getToken();
  await fetchEventSource(`${API_BASE}/conversations/${conversationId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json", // (the library adds `accept: text/event-stream`)
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    credentials: "include",
    signal,
    openWhenHidden: true, // don't abort and re-POST when the tab is hidden
    fetch: (input, init) => globalThis.fetch(input, init),
    async onopen(response) {
      const type = response.headers.get("content-type") ?? "";
      if (response.ok && type.startsWith(EventStreamContentType)) {
        handlers.onOpen?.();
        return;
      }
      if (response.status === 401) throw new NeedsRefresh();
      throw await ApiError.fromResponse(response);
    },
    onmessage(message) {
      // `: ping` heartbeat comments never arrive here.
      if (!message.event || !message.data) return;
      const data: unknown = JSON.parse(message.data);
      switch (message.event) {
        case "status":
          handlers.onStatus?.(data as StatusData);
          break;
        case "agent":
          handlers.onAgent?.(data as AgentData);
          break;
        case "sources":
          handlers.onSources?.(((data as { sources?: Source[] }).sources ?? []) as Source[]);
          break;
        case "token":
          handlers.onToken?.(String((data as { text?: unknown }).text ?? ""));
          break;
        case "result":
          handlers.onResult?.(data as ResultData);
          break;
        case "error":
          handlers.onError?.(data as ErrorData);
          break;
        case "done":
          done = true;
          handlers.onDone?.(data as DoneData);
          break;
      }
    },
    onerror(error) {
      throw error; // rethrow = no automatic retry (it would POST the message again)
    },
  });
  return { done };
}
