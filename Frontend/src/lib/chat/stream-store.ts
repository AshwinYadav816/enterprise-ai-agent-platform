import { streamMessage } from "@/lib/api/sse";
import { toastError } from "@/lib/api/errors";
import type {
  AgentData,
  DoneData,
  ErrorData,
  ResultData,
  SendMessageBody,
  Source,
  StatusData,
} from "@/lib/chat/types";

/**
 * Live chat replies, one per conversation, kept OUTSIDE React state: a stream started on /chat
 * must survive the switch to /chat/[id], and Next keeps hidden routes mounted. Components read it
 * with useSyncExternalStore (see use-chat-stream.ts).
 *
 * Lifecycle: streaming → settling (done / stopped / connection closed; the server copy is being
 * refetched) → cleared by the chat view once the saved reply is on screen. A message the server
 * refused (429, 409, offline…) ends as `failed` and stays visible with Retry.
 */
export type StepStatus = "pending" | "active" | "done" | "failed";
export type Step = { agent: string; status: StepStatus };

export type ChatStream = {
  conversationId: string;
  phase: "streaming" | "settling" | "failed";
  body: SendMessageBody;
  /** The server accepted the message (it is saved). */
  opened: boolean;
  /** "Planning…" until the first agent starts. */
  planning: boolean;
  steps: Step[];
  /** Latest progress text ("Reading part 2 of 5…"). */
  statusLine: string | null;
  text: string;
  sources: Source[];
  results: ResultData[];
  errors: ErrorData[];
  /** The saved assistant message (from `done`). */
  messageId: string | null;
  /** Server message ids on screen when the stream started; a new id means the reply is saved. */
  knownMessageIds: string[];
  stopped: boolean;
  error: unknown;
};

export type StreamEvent =
  | { type: "open" }
  | { type: "status"; data: StatusData }
  | { type: "agent"; data: AgentData }
  | { type: "sources"; data: Source[] }
  | { type: "token"; data: string }
  | { type: "result"; data: ResultData }
  | { type: "error"; data: ErrorData }
  | { type: "done"; data: DoneData };

const PLAN_PREFIX = "Plan: ";

/** Pure reducer: one SSE event → the next stream state. */
export function applyEvent(s: ChatStream, event: StreamEvent): ChatStream {
  switch (event.type) {
    case "open":
      return { ...s, opened: true };
    case "status": {
      const message = event.data.message ?? "";
      if (message.startsWith("Planning")) return { ...s, planning: true, statusLine: null };
      if (message.startsWith(PLAN_PREFIX)) {
        const agents = message
          .slice(PLAN_PREFIX.length)
          .split("→")
          .map((a) => a.trim());
        return {
          ...s,
          steps: agents.filter(Boolean).map((agent) => ({ agent, status: "pending" })),
          statusLine: null,
        };
      }
      return { ...s, statusLine: message };
    }
    case "agent": {
      const index = Math.max(0, event.data.step - 1);
      const steps = [...s.steps];
      while (steps.length <= index) steps.push({ agent: event.data.name, status: "pending" });
      steps[index] = { agent: event.data.name, status: "active" };
      for (let i = 0; i < index; i++) {
        if (steps[i].status === "active" || steps[i].status === "pending") {
          steps[i] = { ...steps[i], status: "done" };
        }
      }
      return { ...s, planning: false, steps, statusLine: null };
    }
    case "sources":
      return { ...s, sources: [...s.sources, ...event.data] };
    case "token":
      return { ...s, planning: false, text: s.text + event.data };
    case "result":
      return { ...s, results: [...s.results, event.data] };
    case "error": {
      const failed = event.data.agent;
      return {
        ...s,
        errors: [...s.errors, event.data],
        steps: failed
          ? s.steps.map((step) =>
              step.agent === failed && step.status !== "done"
                ? { ...step, status: "failed" }
                : step,
            )
          : s.steps,
      };
    }
    case "done":
      return {
        ...s,
        planning: false,
        statusLine: null,
        text: event.data.answer || s.text,
        messageId: event.data.message_id,
        steps: s.steps.map((step) =>
          step.status === "active" || step.status === "pending"
            ? { ...step, status: "done" }
            : step,
        ),
      };
  }
}

// ---- the store

const streams = new Map<string, ChatStream>();
const controllers = new Map<string, AbortController>();
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((listener) => listener());
}

function update(id: string, change: (s: ChatStream) => ChatStream) {
  const current = streams.get(id);
  if (!current) return;
  streams.set(id, change(current));
  emit();
}

export function getStream(id: string | undefined): ChatStream | undefined {
  return id ? streams.get(id) : undefined;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function isStreaming(id: string | undefined): boolean {
  return getStream(id)?.phase === "streaming";
}

type StartOptions = {
  knownMessageIds: string[];
  /** The server saved the question (a first message also titles the conversation). */
  onOpened?: () => void;
  /** Refetch the conversation (messages + list) once the reply is saved or the stream ended. */
  onSettled: () => Promise<unknown>;
};

export function startStream(id: string, body: SendMessageBody, options: StartOptions): void {
  if (isStreaming(id)) return;
  const controller = new AbortController();
  controllers.set(id, controller);
  streams.set(id, {
    conversationId: id,
    phase: "streaming",
    body,
    opened: false,
    planning: true,
    steps: [],
    statusLine: null,
    text: "",
    sources: [],
    results: [],
    errors: [],
    messageId: null,
    knownMessageIds: options.knownMessageIds,
    stopped: false,
    error: null,
  });
  emit();

  const on = (event: StreamEvent) => update(id, (s) => applyEvent(s, event));
  void (async () => {
    try {
      await streamMessage(
        id,
        body,
        {
          onOpen: () => {
            on({ type: "open" });
            options.onOpened?.();
          },
          onStatus: (data) => on({ type: "status", data }),
          onAgent: (data) => on({ type: "agent", data }),
          onSources: (data) => on({ type: "sources", data }),
          onToken: (data) => on({ type: "token", data }),
          onResult: (data) => on({ type: "result", data }),
          onError: (data) => on({ type: "error", data }),
          onDone: (data) => on({ type: "done", data }),
        },
        controller.signal,
      );
      update(id, (s) => ({ ...s, phase: "settling" }));
    } catch (error) {
      toastError(error);
      // Refused before it was saved: keep the bubble with Retry. Broken mid-way: the server saved
      // what it had (status "interrupted"), so settle and show that.
      update(id, (s) => ({ ...s, phase: s.opened ? "settling" : "failed", error }));
    } finally {
      controllers.delete(id);
      await options.onSettled().catch(() => undefined);
    }
  })();
}

/** Stop button: the backend notices the disconnect and saves the partial reply as interrupted. */
export function stopStream(id: string): void {
  update(id, (s) => ({ ...s, stopped: true }));
  controllers.get(id)?.abort();
}

export function clearStream(id: string): void {
  if (streams.delete(id)) emit();
}

/** Logout / session lost: stop everything and forget it. */
export function resetStreams(): void {
  controllers.forEach((controller) => controller.abort());
  controllers.clear();
  streams.clear();
  emit();
}
