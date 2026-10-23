import { beforeEach, describe, expect, it } from "vitest";

import {
  carryNewChatDraft,
  chatDraftName,
  EMPTY_CHAT_DRAFT,
  parseChatDraft,
} from "@/lib/chat/draft";
import { clearDrafts, readStored, storageKey, writeStored } from "@/lib/storage";

const DOC = { id: "d1", filename: "hr_policy.pdf" };
const key = (name: string, user = "u1") => storageKey("draft", user, name);

beforeEach(() => localStorage.clear());

describe("stored drafts", () => {
  it("are scoped per user and removed on sign-out, preferences are kept", () => {
    writeStored(key("chat:new"), { text: "a" });
    writeStored(key("chat:new", "u2"), { text: "b" });
    writeStored(storageKey("pref", "u1", "sidebar-collapsed"), true);
    expect(readStored(key("chat:new"))).toEqual({ text: "a" });
    expect(readStored(key("chat:new", "u2"))).toEqual({ text: "b" });

    clearDrafts();
    expect(readStored(key("chat:new"))).toBeUndefined();
    expect(readStored(key("chat:new", "u2"))).toBeUndefined();
    expect(readStored(storageKey("pref", "u1", "sidebar-collapsed"))).toBe(true);
  });

  it("ignore anything malformed", () => {
    localStorage.setItem(key("chat:new"), "{not json");
    expect(readStored(key("chat:new"))).toBeUndefined();
    expect(parseChatDraft({ text: "hi", docs: [], agent: "hacker", transcript: null })).toBe(
      undefined,
    );
    const draft = parseChatDraft({
      text: "hi",
      docs: [DOC, { id: 3 }],
      agent: "email",
      transcript: null,
    });
    expect(draft).toEqual({ text: "hi", docs: [DOC], agent: "email", transcript: null });
  });
});

describe("carryNewChatDraft", () => {
  it("moves a new chat's documents and agent to its conversation, then empties the new chat", () => {
    writeStored(key(chatDraftName()), {
      ...EMPTY_CHAT_DRAFT,
      text: "sent",
      docs: [DOC],
      agent: "research",
      transcript: "A: hi",
    });
    carryNewChatDraft("u1", "c1");
    expect(readStored(key(chatDraftName("c1")))).toEqual({
      ...EMPTY_CHAT_DRAFT,
      docs: [DOC],
      agent: "research",
    });
    expect(readStored(key(chatDraftName()))).toBeUndefined();
  });

  it("leaves no draft behind when there was nothing to carry", () => {
    writeStored(key(chatDraftName()), { ...EMPTY_CHAT_DRAFT, text: "sent" });
    carryNewChatDraft("u1", "c1");
    expect(readStored(key(chatDraftName("c1")))).toBeUndefined();
    expect(readStored(key(chatDraftName()))).toBeUndefined();
  });
});
