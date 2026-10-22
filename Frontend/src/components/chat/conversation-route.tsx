"use client";

import { useParams } from "next/navigation";

import { ChatView } from "@/components/chat/chat-view";

/** /chat/[id]: one ChatView per conversation (keyed, so state never leaks between them). */
export function ConversationRoute() {
  const { id } = useParams<{ id: string }>();
  return <ChatView key={id} conversationId={id} />;
}
