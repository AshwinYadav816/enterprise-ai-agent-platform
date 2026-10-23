"use client";

import { ArrowUp, FileText, Mic, Square, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { AgentSelect } from "@/components/chat/agent-select";
import { DocPicker } from "@/components/chat/doc-picker";
import { TranscriptAttach, wordCount } from "@/components/chat/transcript-attach";
import { Button } from "@/components/ui/button";
import { chatDraftName, EMPTY_CHAT_DRAFT, parseChatDraft, type ChatDraft } from "@/lib/chat/draft";
import type { SendMessageBody } from "@/lib/chat/types";
import { useStoredState } from "@/lib/hooks/use-stored-state";
import { cn } from "@/lib/utils";

const MAX_CHARS = 8000; // backend SendMessageRequest.content
const MAX_HEIGHT = 200;

type ComposerProps = {
  /** Whose draft this is (undefined: a new chat). The draft survives a refresh. */
  conversationId?: string;
  streaming: boolean;
  /** Resolves true when the message was accepted for sending (then the box is cleared). */
  onSend: (body: SendMessageBody) => Promise<boolean> | boolean;
  onStop: () => void;
  autoFocus?: boolean;
  placeholder?: string;
};

export function Composer({
  conversationId,
  streaming,
  onSend,
  onStop,
  autoFocus,
  placeholder = "Ask about your documents, or give an agent a task…",
}: ComposerProps) {
  const [draft, setDraft] = useStoredState<ChatDraft>(
    "draft",
    chatDraftName(conversationId),
    EMPTY_CHAT_DRAFT,
    parseChatDraft,
  );
  const { text, docs, agent, transcript } = draft;
  const update = (patch: Partial<ChatDraft>) => setDraft((d) => ({ ...d, ...patch }));
  const [sending, setSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hintId = useId();

  // Grow with the text up to MAX_HEIGHT (for browsers without `field-sizing: content`).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [text]);

  const content = text.trim();
  const canSend = content.length > 0 && content.length <= MAX_CHARS && !streaming && !sending;

  const submit = async () => {
    if (!canSend) return;
    setSending(true);
    try {
      const sent = await onSend({
        content,
        doc_ids: docs.length ? docs.map((d) => d.id) : undefined,
        force_agent: agent === "auto" ? undefined : agent,
        transcript: transcript ?? undefined,
      });
      if (sent) {
        // A transcript belongs to one message; documents and agent stay with the conversation.
        // A new chat moves to its own page (which takes them along): this one starts empty.
        setDraft((d) => (conversationId ? { ...d, text: "", transcript: null } : EMPTY_CHAT_DRAFT));
      }
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  };

  return (
    <div className="rounded-xl border border-input bg-card transition-colors focus-within:border-ring">
      {(docs.length > 0 || transcript) && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-3" aria-label="Attached">
          {docs.map((doc) => (
            <Chip
              key={doc.id}
              onRemove={() => update({ docs: docs.filter((d) => d.id !== doc.id) })}
            >
              <FileText className="size-3.5" aria-hidden />
              <span className="max-w-48 truncate">{doc.filename}</span>
            </Chip>
          ))}
          {transcript && (
            <Chip onRemove={() => update({ transcript: null })}>
              <Mic className="size-3.5" aria-hidden />
              Transcript · {wordCount(transcript).toLocaleString()} words
            </Chip>
          )}
        </div>
      )}

      <label htmlFor={hintId} className="sr-only">
        Message
      </label>
      <textarea
        id={hintId}
        ref={textareaRef}
        value={text}
        rows={1}
        autoFocus={autoFocus}
        onChange={(e) => update({ text: e.target.value })}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            void submit();
          }
        }}
        placeholder={placeholder}
        className="block max-h-[200px] min-h-12 w-full resize-none bg-transparent px-4 pt-3 pb-1 text-[0.9375rem] leading-6 outline-none placeholder:text-muted-foreground"
      />

      <div className="flex items-center gap-1 px-2 pb-2">
        <DocPicker value={docs} onChange={(v) => update({ docs: v })} disabled={streaming} />
        <TranscriptAttach
          value={transcript}
          onChange={(v) => update({ transcript: v })}
          disabled={streaming}
        />
        <AgentSelect value={agent} onChange={(v) => update({ agent: v })} disabled={streaming} />
        <span
          className={cn(
            "ml-auto pr-1 type-small text-muted-foreground",
            content.length > MAX_CHARS && "text-destructive",
          )}
          aria-live="polite"
        >
          {content.length > MAX_CHARS * 0.9 ? `${content.length.toLocaleString()} / 8,000` : ""}
        </span>
        {streaming ? (
          <Button size="icon-sm" variant="outline" onClick={onStop} aria-label="Stop generating">
            <Square className="fill-current" />
          </Button>
        ) : (
          <Button
            size="icon-sm"
            onClick={() => void submit()}
            disabled={!canSend}
            aria-label="Send message"
          >
            <ArrowUp />
          </Button>
        )}
      </div>
    </div>
  );
}

function Chip({ children, onRemove }: { children: React.ReactNode; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-background py-0.5 pr-1 pl-2.5 text-xs">
      {children}
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove"
        className="rounded-full p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <X className="size-3" />
      </button>
    </span>
  );
}
