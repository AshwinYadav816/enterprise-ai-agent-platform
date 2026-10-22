import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearToken, setOnAuthLost, setToken } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";
import { streamMessage, type StreamHandlers } from "@/lib/api/sse";

const SSE = { "Content-Type": "text/event-stream" };

/** An SSE response body, delivered in small chunks (frames may be split anywhere). */
function sseResponse(frames: string, chunk = 7): Response {
  const bytes = new TextEncoder().encode(frames);
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunk) controller.enqueue(bytes.slice(i, i + chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: SSE });
}

const frame = (event: string, data: unknown) =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const FULL_STREAM =
  frame("status", { message: "Planning…" }) +
  ": ping\n\n" +
  frame("agent", { name: "research", step: 1, total: 1, instruction: "q" }) +
  frame("sources", {
    sources: [{ n: 1, doc_id: "d1", filename: "a.pdf", page: 2, snippet: "s" }],
  }) +
  frame("token", { text: "Hello " }) +
  frame("token", { text: "world [1]" }) +
  frame("result", { agent: "research", output: { answer: "Hello world [1]" } }) +
  frame("error", { message: "A step failed", agent: "email" }) +
  frame("done", { answer: "Hello world [1]", agents: ["research"], errors: 1, message_id: "m1" });

function recorder() {
  const calls: [string, unknown][] = [];
  const handlers: StreamHandlers = {
    onOpen: () => calls.push(["open", null]),
    onStatus: (d) => calls.push(["status", d]),
    onAgent: (d) => calls.push(["agent", d]),
    onSources: (d) => calls.push(["sources", d]),
    onToken: (d) => calls.push(["token", d]),
    onResult: (d) => calls.push(["result", d]),
    onError: (d) => calls.push(["error", d]),
    onDone: (d) => calls.push(["done", d]),
  };
  return { calls, handlers };
}

const body = { content: "hi" };

beforeEach(() => {
  setToken("t1");
  setOnAuthLost(null);
});
afterEach(() => {
  clearToken();
  vi.unstubAllGlobals();
});

describe("streamMessage", () => {
  it("POSTs with the token and dispatches every event type in order (pings ignored)", async () => {
    const fetchMock = vi.fn(async () => sseResponse(FULL_STREAM));
    vi.stubGlobal("fetch", fetchMock);
    const { calls, handlers } = recorder();

    const outcome = await streamMessage("c1", body, handlers, new AbortController().signal);

    expect(outcome).toEqual({ done: true });
    expect(calls.map(([type]) => type)).toEqual([
      "open",
      "status",
      "agent",
      "sources",
      "token",
      "token",
      "result",
      "error",
      "done",
    ]);
    expect(calls[4]).toEqual(["token", "Hello "]);
    expect(calls[3][1]).toEqual([{ n: 1, doc_id: "d1", filename: "a.pdf", page: 2, snippet: "s" }]);
    expect(calls[8][1]).toMatchObject({ message_id: "m1" });

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.test/api/v1/conversations/c1/messages");
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"content":"hi"}');
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t1");
    expect(init.credentials).toBe("include");
  });

  it("reports done: false when the stream closes without a done event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sseResponse(frame("token", { text: "par" }))),
    );
    const outcome = await streamMessage(
      "c1",
      body,
      recorder().handlers,
      new AbortController().signal,
    );
    expect(outcome).toEqual({ done: false });
  });

  it("on 401 refreshes once and retries the whole call once", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) {
        return json(200, {
          access_token: "t2",
          token_type: "bearer",
          expires_in: 900,
          must_change_password: false,
          user: { id: "u" },
        });
      }
      const auth = (init?.headers as Record<string, string>).Authorization;
      return auth === "Bearer t2"
        ? sseResponse(FULL_STREAM)
        : json(401, { error: { code: "x", message: "x" } });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { calls, handlers } = recorder();

    const outcome = await streamMessage("c1", body, handlers, new AbortController().signal);

    expect(outcome.done).toBe(true);
    const urls = fetchMock.mock.calls.map(([u]) => String(u).replace("http://api.test/api/v1", ""));
    expect(urls).toEqual([
      "/conversations/c1/messages",
      "/auth/refresh",
      "/conversations/c1/messages",
    ]);
    expect(calls.filter(([t]) => t === "open")).toHaveLength(1);
  });

  it("gives up when the refresh is rejected: onAuthLost + ApiError 401", async () => {
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);
    const fetchMock = vi.fn(async () =>
      json(401, { error: { code: "unauthorized", message: "no" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      streamMessage("c1", body, recorder().handlers, new AbortController().signal),
    ).rejects.toMatchObject({ status: 401 });
    expect(onAuthLost).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2); // message + refresh, no second message POST
  });

  it("turns a refused message into ApiError and never re-POSTs it", async () => {
    const fetchMock = vi.fn(async () =>
      json(429, { error: { code: "rate_limited", message: "Too many requests" } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const error = await streamMessage(
      "c1",
      body,
      recorder().handlers,
      new AbortController().signal,
    ).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 429, code: "rate_limited" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("does not retry after a network failure", async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      streamMessage("c1", body, recorder().handlers, new AbortController().signal),
    ).rejects.toThrow("Failed to fetch");
    await new Promise((r) => setTimeout(r, 1200)); // longer than the library's retry interval
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stop: aborting resolves with done: false", async () => {
    const controller = new AbortController();
    const body$ = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode(frame("token", { text: "Hel" })));
        // never closes: only the abort ends it
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(body$, { status: 200, headers: SSE })),
    );
    const { calls, handlers } = recorder();
    const pending = streamMessage("c1", body, handlers, controller.signal);
    await vi.waitFor(() => expect(calls.some(([t]) => t === "token")).toBe(true));
    controller.abort();
    await expect(pending).resolves.toEqual({ done: false });
  });
});
