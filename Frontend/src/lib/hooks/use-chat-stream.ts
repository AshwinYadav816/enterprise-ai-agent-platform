"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useCallback, useSyncExternalStore } from "react";

import { toastError } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import { carryNewChatDraft } from "@/lib/chat/draft";
import {
  getStream,
  startStream,
  stopStream,
  subscribe,
  type ChatStream,
} from "@/lib/chat/stream-store";
import type { SendMessageBody } from "@/lib/chat/types";
import { createConversation } from "@/lib/hooks/use-conversations";
import { useAuth } from "@/providers/auth-provider";

/**
 * The live reply of one conversation + send/stop. Without a conversation id (/chat), `send`
 * creates the conversation, starts streaming and moves to /chat/[id], where the same stream
 * is picked up from the store.
 */
export function useChatStream(conversationId: string | undefined) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const { user } = useAuth();
  const stream: ChatStream | undefined = useSyncExternalStore(
    subscribe,
    () => getStream(conversationId),
    () => undefined,
  );

  const send = useCallback(
    async (body: SendMessageBody, knownMessageIds: string[] = []) => {
      let id = conversationId;
      if (!id) {
        try {
          id = (await createConversation()).id;
        } catch (error) {
          toastError(error);
          return false;
        }
      }
      const target = id;
      startStream(target, body, {
        knownMessageIds,
        onOpened: () => void queryClient.invalidateQueries({ queryKey: keys.conversations.all }),
        onSettled: () =>
          Promise.all([
            queryClient.invalidateQueries({ queryKey: keys.messages.list(target) }),
            queryClient.invalidateQueries({ queryKey: keys.conversations.all }),
          ]),
      });
      if (!conversationId) {
        if (user) carryNewChatDraft(user.id, target); // before its page reads the draft
        router.replace(`/chat/${target}`);
      }
      return true;
    },
    [conversationId, queryClient, router, user],
  );

  const stop = useCallback(() => {
    if (conversationId) stopStream(conversationId);
  }, [conversationId]);

  return { stream, send, stop };
}
