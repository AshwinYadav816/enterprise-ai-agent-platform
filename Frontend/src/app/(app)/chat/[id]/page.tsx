import type { Metadata } from "next";

import { ConversationRoute } from "@/components/chat/conversation-route";

export const metadata: Metadata = { title: "Chat" };

export default function ConversationPage() {
  return <ConversationRoute />;
}
