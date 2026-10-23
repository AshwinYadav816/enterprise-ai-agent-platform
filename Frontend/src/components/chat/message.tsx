"use client";

import { AlertTriangle, FileText, Mic, RotateCw, Square } from "lucide-react";

import { AgentStatus } from "@/components/chat/agent-status";
import { Markdown } from "@/components/chat/markdown";
import { CopyButton, hasCard, ResultCard } from "@/components/chat/result-card";
import { SourcesFooter } from "@/components/chat/sources-footer";
import { Button } from "@/components/ui/button";
import { citableText, citedSources } from "@/lib/chat/citations";
import type { Step } from "@/lib/chat/stream-store";
import type { ErrorData, ResultData, Source } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

export type AssistantView = {
  status: "streaming" | "settling" | "complete" | "interrupted" | "error";
  content: string;
  agents: string[];
  sources: Source[];
  results: ResultData[];
  errors: ErrorData[];
  messageId: string | null;
  live?: { planning: boolean; steps: Step[]; statusLine: string | null };
};

export function UserMessage({
  content,
  docCount = 0,
  hasTranscript = false,
  failed,
}: {
  content: string;
  docCount?: number;
  hasTranscript?: boolean;
  /** Shown when the server refused the message (rate limit, offline…). */
  failed?: { message: string; onRetry: () => void; onDismiss: () => void };
}) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div
        className={cn(
          "max-w-[85%] rounded-2xl rounded-br-md bg-blue-tint px-4 py-2.5 whitespace-pre-wrap text-foreground sm:max-w-[75%]",
          failed && "opacity-70",
        )}
      >
        {content}
      </div>
      {(docCount > 0 || hasTranscript) && (
        <p className="flex gap-3 type-small text-muted-foreground">
          {docCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <FileText className="size-3.5" aria-hidden />
              {docCount} {docCount === 1 ? "document" : "documents"}
            </span>
          )}
          {hasTranscript && (
            <span className="inline-flex items-center gap-1">
              <Mic className="size-3.5" aria-hidden /> Transcript attached
            </span>
          )}
        </p>
      )}
      {failed && (
        <div
          className="flex flex-wrap items-center justify-end gap-2 type-small text-destructive"
          role="alert"
        >
          <AlertTriangle className="size-3.5" aria-hidden />
          <span>Not sent: {failed.message}</span>
          <Button variant="outline" size="xs" onClick={failed.onRetry}>
            <RotateCw /> Retry
          </Button>
          <Button variant="ghost" size="xs" onClick={failed.onDismiss}>
            Dismiss
          </Button>
        </div>
      )}
    </div>
  );
}

export function AssistantMessage({
  view,
  conversationId,
  onRetry,
}: {
  view: AssistantView;
  conversationId: string;
  onRetry?: () => void;
}) {
  const streaming = view.status === "streaming";
  const cards = view.results
    .map((result, index) => ({ result, index }))
    .filter(({ result }) => hasCard(result));
  // One meeting/email/report/document step: the text is just the card's summary again.
  const cardIsTheAnswer =
    !streaming &&
    cards.length === 1 &&
    view.agents.length === 1 &&
    view.agents[0] === cards[0].result.agent;

  return (
    <article className="group/message" aria-busy={streaming || undefined}>
      {view.live ? (
        <AgentStatus
          live
          planning={view.live.planning}
          steps={view.live.steps}
          statusLine={view.live.statusLine}
        />
      ) : (
        <AgentStatus live={false} agents={view.agents} />
      )}

      {(streaming || (view.content && !cardIsTheAnswer)) && (
        <Markdown sources={view.sources} cursor={streaming} className="type-answer">
          {view.content}
        </Markdown>
      )}

      {cards.map(({ result, index }) => (
        <ResultCard
          key={index}
          result={result}
          pdfPath={
            view.messageId
              ? `/conversations/${conversationId}/messages/${view.messageId}/results/${index}/pdf`
              : undefined
          }
        />
      ))}

      {view.errors.map((error, i) => (
        <p key={i} className="mt-2 flex items-start gap-1.5 font-sans type-small text-destructive">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          {error.message}
        </p>
      ))}

      {view.status === "interrupted" && (
        <p className="mt-2 flex items-center gap-1.5 font-sans type-small text-muted-foreground">
          <Square className="size-3" aria-hidden /> Stopped before the answer was finished.
        </p>
      )}
      {view.status === "error" && (
        <p className="mt-2 flex items-center gap-1.5 font-sans type-small text-destructive">
          <AlertTriangle className="size-3.5" aria-hidden /> Something went wrong with this answer.
        </p>
      )}

      <SourcesFooter
        sources={citedSources(view.sources, [view.content, ...view.results.map(citableText)])}
      />

      {!streaming && view.status !== "settling" && (
        <div className="mt-2 flex gap-1 font-sans opacity-100 transition-opacity duration-150 md:opacity-0 md:group-focus-within/message:opacity-100 md:group-hover/message:opacity-100">
          {view.content && <CopyButton text={view.content} label="Copy" />}
          {onRetry && (view.status === "interrupted" || view.status === "error") && (
            <Button variant="ghost" size="sm" onClick={onRetry}>
              <RotateCw /> Retry
            </Button>
          )}
        </div>
      )}
    </article>
  );
}
