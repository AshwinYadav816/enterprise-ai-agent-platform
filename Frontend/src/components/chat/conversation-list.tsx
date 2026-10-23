"use client";

import { Ellipsis, Loader2, MessageSquare, Pencil, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState, useSyncExternalStore } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { isStreaming, subscribe } from "@/lib/chat/stream-store";
import type { Conversation } from "@/lib/chat/types";
import {
  conversationTitle,
  groupConversations,
  useConversations,
  useDeleteConversation,
  useRenameConversation,
} from "@/lib/hooks/use-conversations";
import { useStoredState } from "@/lib/hooks/use-stored-state";
import { asString } from "@/lib/storage";
import { cn } from "@/lib/utils";

/** Conversation history: search, grouped by recency, rename inline, delete with confirm. */
export function ConversationList({
  onNavigate,
  showNewChat = true,
}: {
  onNavigate?: () => void;
  /** The desktop sidebar already has "New chat"; the phone sheet needs its own. */
  showNewChat?: boolean;
}) {
  const { id: activeId } = useParams<{ id?: string }>();
  const router = useRouter();
  const query = useConversations();
  const [search, setSearch] = useStoredState("draft", "chat:search", "", asString);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Conversation | null>(null);
  const remove = useDeleteConversation();

  const needle = search.trim().toLowerCase();
  const visible = needle
    ? query.conversations.filter((c) => conversationTitle(c).toLowerCase().includes(needle))
    : query.conversations;
  const groups = groupConversations(visible);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-2 p-3">
        {showNewChat && (
          <Button asChild variant="outline" className="w-full justify-start">
            <Link href="/chat" onClick={onNavigate}>
              <Plus /> New chat
            </Link>
          </Button>
        )}
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
            className="h-8 pl-8"
          />
        </div>
      </div>

      <nav aria-label="Conversations" className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {query.isPending ? (
          <div className="space-y-2" aria-busy="true">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : query.isError ? (
          <p className="px-2 py-4 text-sm text-muted-foreground">
            Couldn&apos;t load conversations.{" "}
            <button className="text-primary underline" onClick={() => void query.refetch()}>
              Retry
            </button>
          </p>
        ) : groups.length === 0 ? (
          <p className="flex flex-col items-center gap-2 px-2 py-8 text-center text-sm text-muted-foreground">
            <MessageSquare className="size-5" aria-hidden />
            {needle ? "No conversations match." : "Your conversations will appear here."}
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="mb-1 px-2 type-eyebrow text-muted-foreground">{group.label}</p>
              <ul className="space-y-0.5">
                {group.items.map((conversation) => (
                  <li key={conversation.id}>
                    {renaming === conversation.id ? (
                      <RenameField conversation={conversation} onDone={() => setRenaming(null)} />
                    ) : (
                      <ConversationItem
                        conversation={conversation}
                        active={conversation.id === activeId}
                        onNavigate={onNavigate}
                        onRename={() => setRenaming(conversation.id)}
                        onDelete={() => setToDelete(conversation)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
        {query.hasNextPage && !needle && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => void query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
          >
            {query.isFetchingNextPage && <Loader2 className="animate-spin" aria-hidden />}
            Load more
          </Button>
        )}
      </nav>

      <AlertDialog open={toDelete !== null} onOpenChange={(open) => !open && setToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{toDelete ? conversationTitle(toDelete) : ""}&rdquo; and all its messages will
              be removed. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={remove.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (!toDelete) return;
                const id = toDelete.id;
                remove.mutate(id, {
                  onSuccess: () => {
                    setToDelete(null);
                    if (id === activeId) router.push("/chat");
                  },
                });
              }}
            >
              {remove.isPending ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ConversationItem({
  conversation,
  active,
  onNavigate,
  onRename,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  onNavigate?: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const title = conversationTitle(conversation);
  const streaming = useSyncExternalStore(
    subscribe,
    () => isStreaming(conversation.id),
    () => false,
  );

  return (
    <div
      className={cn(
        "group/item relative flex items-center rounded-md transition-colors duration-150",
        active
          ? "bg-blue-tint text-primary before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-coral"
          : "hover:bg-accent",
      )}
    >
      <Link
        href={`/chat/${conversation.id}`}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2 py-1.5 pr-1 pl-3 text-sm",
          active && "font-medium",
        )}
        title={title}
      >
        <span className="truncate">{title}</span>
        {streaming && (
          <span
            className="size-1.5 shrink-0 animate-pulse rounded-full bg-coral"
            aria-label="Answering"
          />
        )}
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={`Options for ${title}`}
            className="mr-1 shrink-0 opacity-100 hover:bg-background/60 data-[state=open]:opacity-100 md:opacity-0 md:group-focus-within/item:opacity-100 md:group-hover/item:opacity-100"
          >
            <Ellipsis />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem onSelect={onRename}>
            <Pencil /> Rename
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={onDelete}>
            <Trash2 /> Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

function RenameField({ conversation, onDone }: { conversation: Conversation; onDone: () => void }) {
  const [title, setTitle] = useState(conversationTitle(conversation));
  const rename = useRenameConversation();
  const finished = useRef(false); // Enter saves, then the unmount blurs: save only once
  const save = () => {
    if (finished.current) return;
    finished.current = true;
    const next = title.trim();
    if (next && next !== conversation.title) rename.mutate({ id: conversation.id, title: next });
    onDone();
  };
  return (
    <Input
      autoFocus
      value={title}
      maxLength={200}
      aria-label="Conversation title"
      onChange={(e) => setTitle(e.target.value)}
      onFocus={(e) => e.target.select()}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") {
          finished.current = true;
          onDone();
        }
      }}
      className="h-8"
    />
  );
}
