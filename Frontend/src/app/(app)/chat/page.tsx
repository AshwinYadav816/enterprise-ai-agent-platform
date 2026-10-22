import { MessageSquare } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Chat" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Assistant"
        title="Chat"
        description="Ask questions about your documents, or hand a task to an agent."
      />
      <EmptyState
        icon={MessageSquare}
        title="Start a conversation"
        description="Streaming chat arrives in Phase 4."
      />
    </div>
  );
}
