import { ConversationList } from "@/components/chat/conversation-list";

/** Two columns on desktop: conversation history | the open conversation. */
export default function ChatLayout({ children }: LayoutProps<"/chat">) {
  return (
    <div className="flex h-full min-h-0">
      <aside
        aria-label="Conversation history"
        className="hidden w-72 shrink-0 flex-col border-r bg-background lg:flex"
      >
        <ConversationList showNewChat={false} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
