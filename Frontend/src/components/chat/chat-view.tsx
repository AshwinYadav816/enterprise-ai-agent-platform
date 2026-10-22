"use client";

import { useQueryClient } from "@tanstack/react-query";
import { FileSearch, ListChecks, Mail, PanelLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState } from "@/components/common/error-state";
import { Composer } from "@/components/chat/composer";
import { ConversationList } from "@/components/chat/conversation-list";
import { AssistantMessage, UserMessage, type AssistantView } from "@/components/chat/message";
import { MessageList } from "@/components/chat/message-list";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, errorMessage } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import { clearStream, type ChatStream } from "@/lib/chat/stream-store";
import { asResults, asSources, type Message, type SendMessageBody } from "@/lib/chat/types";
import { useChatStream } from "@/lib/hooks/use-chat-stream";
import { conversationTitle, useConversations, useMessages } from "@/lib/hooks/use-conversations";

const SUGGESTIONS = [
  { icon: FileSearch, text: "What does our leave policy say about carrying over days?" },
  { icon: ListChecks, text: "Write a weekly report from my documents" },
  { icon: Mail, text: "Draft a friendly email inviting the team to Friday's demo" },
];

/** A conversation (or, without an id, a new one: the first send creates it). */
export function ChatView({ conversationId }: { conversationId?: string }) {
  const queryClient = useQueryClient();
  const history = useMessages(conversationId);
  const { stream, send, stop } = useChatStream(conversationId);
  const { conversations } = useConversations();
  const [listOpen, setListOpen] = useState(false);

  const messages = history.messages;
  const knownIds = useMemo(() => messages.map((m) => m.id), [messages]);
  const caughtUp = stream ? serverHasReply(stream, messages) : false;
  useSettleStream(stream, caughtUp, conversationId, queryClient);

  const conversation = conversations.find((c) => c.id === conversationId);
  const title = conversation ? conversationTitle(conversation) : conversationId ? "" : "New chat";
  const streaming = stream?.phase === "streaming";

  const onSend = (body: SendMessageBody) => send(body, knownIds);
  const retry = (index: number) => {
    const question = [...messages.slice(0, index)].reverse().find((m) => m.role === "user");
    if (question) void send({ content: question.content }, knownIds);
  };

  const notFound = history.error instanceof ApiError && history.error.status === 404;
  const empty = !conversationId || (history.isSuccess && messages.length === 0 && !stream);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3 md:px-4">
        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={() => setListOpen(true)}
          aria-label="Show conversations"
        >
          <PanelLeft />
        </Button>
        <h1 className="min-w-0 truncate font-serif text-lg font-semibold">{title}</h1>
      </header>

      {notFound ? (
        <div className="p-6">
          <ErrorState title="This conversation doesn't exist" error={history.error} />
          <div className="mt-4 flex justify-center">
            <Button asChild>
              <Link href="/chat">Start a new chat</Link>
            </Button>
          </div>
        </div>
      ) : history.isError ? (
        <div className="p-6">
          <ErrorState
            title="Couldn't load this conversation"
            error={history.error}
            onRetry={() => void history.refetch()}
          />
        </div>
      ) : conversationId && history.isPending ? (
        <MessagesSkeleton />
      ) : empty ? (
        <Welcome onPick={(text) => void onSend({ content: text })} />
      ) : (
        <MessageList
          hasEarlier={!!history.hasNextPage}
          loadingEarlier={history.isFetchingNextPage}
          onLoadEarlier={() => history.fetchNextPage()}
        >
          {messages.map((message, index) =>
            message.role === "user" ? (
              <UserMessage key={message.id} content={message.content} />
            ) : (
              <AssistantMessage
                key={message.id}
                view={savedView(message)}
                conversationId={conversationId!}
                onRetry={() => retry(index)}
              />
            ),
          )}
          {stream && !caughtUp && (
            <DraftTurn
              stream={stream}
              messages={messages}
              conversationId={conversationId!}
              onSend={onSend}
            />
          )}
        </MessageList>
      )}

      <div className="shrink-0 px-3 pb-3 md:px-6 md:pb-5">
        <div className="mx-auto w-full max-w-[760px]">
          <Composer
            streaming={streaming}
            onSend={onSend}
            onStop={stop}
            autoFocus={!conversationId}
          />
          <p className="mt-1.5 text-center type-small text-muted-foreground">
            Answers can be wrong. Check the sources for anything important.
          </p>
        </div>
      </div>

      <Sheet open={listOpen} onOpenChange={setListOpen}>
        <SheetContent
          side="left"
          className="flex w-80 flex-col gap-0 p-0"
          aria-describedby={undefined}
        >
          <div className="flex h-12 items-center border-b px-4">
            <SheetTitle className="font-serif text-lg">Conversations</SheetTitle>
          </div>
          <ConversationList onNavigate={() => setListOpen(false)} />
        </SheetContent>
      </Sheet>
    </div>
  );
}

/** The optimistic question + the live (or just finished) answer. */
function DraftTurn({
  stream,
  messages,
  conversationId,
  onSend,
}: {
  stream: ChatStream;
  messages: Message[];
  conversationId: string;
  onSend: (body: SendMessageBody) => void;
}) {
  const known = new Set(stream.knownMessageIds);
  const questionSaved = messages.some((m) => m.role === "user" && !known.has(m.id));
  const failed = stream.phase === "failed";

  return (
    <>
      {!questionSaved && (
        <UserMessage
          content={stream.body.content}
          docCount={stream.body.doc_ids?.length ?? 0}
          hasTranscript={!!stream.body.transcript}
          failed={
            failed
              ? {
                  message: errorMessage(stream.error),
                  onRetry: () => {
                    clearStream(conversationId);
                    onSend(stream.body);
                  },
                  onDismiss: () => clearStream(conversationId),
                }
              : undefined
          }
        />
      )}
      {!failed && <AssistantMessage view={liveView(stream)} conversationId={conversationId} />}
    </>
  );
}

function liveView(stream: ChatStream): AssistantView {
  const streaming = stream.phase === "streaming";
  return {
    status: streaming ? "streaming" : stream.stopped ? "interrupted" : "settling",
    content: stream.text,
    agents: stream.steps.map((s) => s.agent),
    sources: stream.sources,
    results: stream.results,
    errors: stream.errors,
    messageId: stream.messageId,
    live: streaming
      ? { planning: stream.planning, steps: stream.steps, statusLine: stream.statusLine }
      : undefined,
  };
}

function savedView(message: Message): AssistantView {
  return {
    status: message.status === "complete" ? "complete" : message.status,
    content: message.content,
    agents: message.agent ? message.agent.split(",") : [],
    sources: asSources(message.sources),
    results: asResults(message.results),
    errors: [],
    messageId: message.id,
  };
}

/** The saved reply is on screen: the server copy replaces the draft. */
function serverHasReply(stream: ChatStream, messages: Message[]): boolean {
  if (stream.phase === "streaming" || stream.phase === "failed") return false;
  if (stream.messageId && messages.some((m) => m.id === stream.messageId)) return true;
  const known = new Set(stream.knownMessageIds);
  return messages.some((m) => m.role === "assistant" && !known.has(m.id));
}

/**
 * After a stream ends, drop the draft once the saved reply has been fetched. A stopped reply is
 * saved a moment after the disconnect, so refetch a few times until it shows up.
 */
function useSettleStream(
  stream: ChatStream | undefined,
  caughtUp: boolean,
  conversationId: string | undefined,
  queryClient: ReturnType<typeof useQueryClient>,
) {
  const attempts = useRef(0);
  const settling = stream?.phase === "settling";
  useEffect(() => {
    if (!conversationId || !settling) {
      attempts.current = 0;
      return;
    }
    if (caughtUp || attempts.current >= 5) {
      clearStream(conversationId);
      return;
    }
    const timer = setTimeout(() => {
      attempts.current += 1;
      void queryClient.invalidateQueries({ queryKey: keys.messages.list(conversationId) });
    }, 800);
    return () => clearTimeout(timer);
  }, [settling, caughtUp, conversationId, queryClient, stream]);
}

function Welcome({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-10 text-center">
      <p className="type-eyebrow text-muted-foreground">Assistant</p>
      <h2 className="mt-2 max-w-xl type-display text-balance">What can I help you with today?</h2>
      <p className="mt-2 max-w-md text-muted-foreground">
        Ask about your documents, or hand a task to the meeting, report, email or research agent.
      </p>
      <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
        {SUGGESTIONS.map(({ icon: Icon, text }) => (
          <button
            key={text}
            type="button"
            onClick={() => onPick(text)}
            className="flex flex-col items-start gap-2 rounded-lg border bg-card p-4 text-left text-sm transition-colors duration-150 hover:border-primary/40 hover:bg-accent"
          >
            <Icon className="size-4 text-primary" aria-hidden />
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessagesSkeleton() {
  return (
    <div
      className="mx-auto w-full max-w-[760px] flex-1 space-y-8 px-4 py-6 md:px-6"
      aria-busy="true"
    >
      <span className="sr-only" role="status">
        Loading messages…
      </span>
      <Skeleton className="ml-auto h-10 w-2/3 rounded-2xl" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-3/5" />
      </div>
    </div>
  );
}
