import { FORCEABLE_AGENTS, type AgentName } from "@/lib/chat/types";
import { asRecord, asString, readStored, storageKey, writeStored } from "@/lib/storage";

export type DraftDoc = { id: string; filename: string };
export type AgentChoice = AgentName | "auto";

/** What the composer holds for one conversation ("new" for /chat) until it is sent. */
export type ChatDraft = {
  text: string;
  docs: DraftDoc[];
  agent: AgentChoice;
  transcript: string | null;
};

export const EMPTY_CHAT_DRAFT: ChatDraft = { text: "", docs: [], agent: "auto", transcript: null };

export const chatDraftName = (conversationId?: string) => `chat:${conversationId ?? "new"}`;

const isDoc = (d: unknown): d is DraftDoc =>
  typeof d === "object" &&
  d !== null &&
  typeof (d as DraftDoc).id === "string" &&
  typeof (d as DraftDoc).filename === "string";

/** A stored list of picked documents (malformed entries dropped). */
export const parseDraftDocs = (v: unknown) => (Array.isArray(v) ? v.filter(isDoc) : undefined);

export const parseChatDraft = asRecord<ChatDraft>({
  text: asString,
  docs: parseDraftDocs,
  agent: (v) =>
    v === "auto" || FORCEABLE_AGENTS.includes(v as AgentName) ? (v as AgentChoice) : undefined,
  transcript: (v) => (v === null ? null : asString(v)),
});

/**
 * The first message of a new chat moves to /chat/[id]: keep its documents and agent for the
 * rest of that conversation (as within a conversation), and start the next new chat empty.
 */
export function carryNewChatDraft(userId: string, conversationId: string): void {
  const newKey = storageKey("draft", userId, chatDraftName());
  const draft = parseChatDraft(readStored(newKey));
  if (draft && (draft.docs.length > 0 || draft.agent !== "auto")) {
    const next: ChatDraft = { ...EMPTY_CHAT_DRAFT, docs: draft.docs, agent: draft.agent };
    writeStored(storageKey("draft", userId, chatDraftName(conversationId)), next);
  }
  writeStored(newKey, undefined);
}

/** A deleted conversation's unsent draft goes with it. */
export function dropChatDraft(userId: string, conversationId: string): void {
  writeStored(storageKey("draft", userId, chatDraftName(conversationId)), undefined);
}
