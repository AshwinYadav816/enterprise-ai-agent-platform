import { describe, expect, it } from "vitest";

import { groupConversations } from "@/lib/hooks/use-conversations";
import { applyEvent, type ChatStream, type StreamEvent } from "@/lib/chat/stream-store";

function fresh(): ChatStream {
  return {
    conversationId: "c1",
    phase: "streaming",
    body: { content: "q" },
    opened: false,
    planning: true,
    steps: [],
    statusLine: null,
    text: "",
    sources: [],
    results: [],
    errors: [],
    messageId: null,
    knownMessageIds: [],
    stopped: false,
    error: null,
  };
}

const run = (events: StreamEvent[]) => events.reduce(applyEvent, fresh());

describe("applyEvent", () => {
  it("builds the plan, the active step and the status line (meeting → email)", () => {
    const s = run([
      { type: "open" },
      { type: "status", data: { message: "Planning…" } },
      { type: "status", data: { message: "Plan: meeting → email" } },
      { type: "agent", data: { name: "meeting", step: 1, total: 2 } },
      { type: "status", data: { message: "Reading transcript part 1 of 3…" } },
    ]);
    expect(s.opened).toBe(true);
    expect(s.planning).toBe(false);
    expect(s.steps).toEqual([
      { agent: "meeting", status: "active" },
      { agent: "email", status: "pending" },
    ]);
    expect(s.statusLine).toBe("Reading transcript part 1 of 3…");

    const next = applyEvent(s, { type: "agent", data: { name: "email", step: 2, total: 2 } });
    expect(next.steps.map((x) => x.status)).toEqual(["done", "active"]);
    expect(next.statusLine).toBeNull();
  });

  it("accumulates tokens, sources and results; done replaces the text and marks steps done", () => {
    const s = run([
      { type: "agent", data: { name: "research", step: 1, total: 1 } },
      { type: "sources", data: [{ n: 1, doc_id: "d", filename: "a.pdf", snippet: "x" }] },
      { type: "token", data: "Hello " },
      { type: "token", data: "world" },
      { type: "result", data: { agent: "research", output: {} } },
      {
        type: "done",
        data: { answer: "Hello world [1]", agents: ["research"], errors: 0, message_id: "m1" },
      },
    ]);
    expect(s.text).toBe("Hello world [1]");
    expect(s.sources).toHaveLength(1);
    expect(s.results).toHaveLength(1);
    expect(s.messageId).toBe("m1");
    expect(s.steps).toEqual([{ agent: "research", status: "done" }]);
  });

  it("marks the failing step and keeps going", () => {
    const s = run([
      { type: "status", data: { message: "Plan: meeting → email" } },
      { type: "agent", data: { name: "meeting", step: 1, total: 2 } },
      { type: "error", data: { message: "The meeting step failed.", agent: "meeting" } },
      { type: "agent", data: { name: "email", step: 2, total: 2 } },
    ]);
    expect(s.steps.map((x) => x.status)).toEqual(["failed", "active"]);
    expect(s.errors).toEqual([{ message: "The meeting step failed.", agent: "meeting" }]);
  });

  it("keeps a non-streaming agent's answer for done (meeting has no tokens)", () => {
    const s = run([
      { type: "agent", data: { name: "meeting", step: 1, total: 1 } },
      { type: "result", data: { agent: "meeting", output: { summary: "We agreed." } } },
      {
        type: "done",
        data: { answer: "We agreed.", agents: ["meeting"], errors: 0, message_id: "m2" },
      },
    ]);
    expect(s.text).toBe("We agreed.");
  });
});

describe("groupConversations", () => {
  it("groups by Today / Previous 7 days / Older", () => {
    const now = new Date(2026, 9, 22, 15, 0);
    const at = (d: Date) => ({
      id: d.toISOString(),
      title: null,
      created_at: "",
      updated_at: d.toISOString(),
    });
    const groups = groupConversations(
      [
        at(new Date(2026, 9, 22, 9, 0)),
        at(new Date(2026, 9, 21, 23, 0)),
        at(new Date(2026, 9, 16, 12, 0)),
        at(new Date(2026, 9, 1, 12, 0)),
      ],
      now,
    );
    expect(groups.map((g) => [g.label, g.items.length])).toEqual([
      ["Today", 1],
      ["Previous 7 days", 2],
      ["Older", 1],
    ]);
  });
});
