"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import type { Conversation, Message } from "@/lib/chat/types";

const CONVERSATIONS_PAGE = 30;
const MESSAGES_PAGE = 30;

/** Your conversations, most recently active first. */
export function useConversations() {
  const query = useInfiniteQuery({
    queryKey: keys.conversations.list(),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/conversations", {
          params: { query: { cursor: pageParam, limit: CONVERSATIONS_PAGE } },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const conversations = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );
  return { ...query, conversations };
}

/**
 * A conversation's history, oldest → newest for display. Pages are fetched newest-first
 * (`order=desc`), so the chat opens at the latest messages; fetchNextPage = "Load earlier".
 */
export function useMessages(conversationId: string | undefined) {
  const query = useInfiniteQuery({
    queryKey: keys.messages.list(conversationId ?? ""),
    enabled: !!conversationId,
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/conversations/{conversation_id}/messages", {
          params: {
            path: { conversation_id: conversationId! },
            query: { cursor: pageParam, limit: MESSAGES_PAGE, order: "desc" },
          },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: Infinity, // changes only through our own sends, which invalidate it
  });
  const messages = useMemo<Message[]>(
    () => (query.data?.pages.flatMap((page) => page.items) ?? []).slice().reverse(),
    [query.data],
  );
  return { ...query, messages };
}

export async function createConversation(): Promise<Conversation> {
  return unwrap(await api.POST("/api/v1/conversations", { body: {} }));
}

export function useRenameConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, title }: { id: string; title: string }) =>
      unwrap(
        await api.PATCH("/api/v1/conversations/{conversation_id}", {
          params: { path: { conversation_id: id } },
          body: { title },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.conversations.all }),
  });
}

export function useDeleteConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(
        await api.DELETE("/api/v1/conversations/{conversation_id}", {
          params: { path: { conversation_id: id } },
        }),
      );
      return id;
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: keys.messages.list(id) });
      return queryClient.invalidateQueries({ queryKey: keys.conversations.all });
    },
  });
}

export type ConversationGroup = { label: string; items: Conversation[] };

/** Today / Previous 7 days / Older, by last activity (local time). */
export function groupConversations(items: Conversation[], now = new Date()): ConversationGroup[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const weekAgo = startOfToday - 7 * 24 * 60 * 60 * 1000;
  const groups: ConversationGroup[] = [
    { label: "Today", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const conversation of items) {
    const at = new Date(conversation.updated_at).getTime();
    const group = at >= startOfToday ? 0 : at >= weekAgo ? 1 : 2;
    groups[group].items.push(conversation);
  }
  return groups.filter((group) => group.items.length > 0);
}

export const conversationTitle = (c: Pick<Conversation, "title">) =>
  c.title?.trim() || "New conversation";
