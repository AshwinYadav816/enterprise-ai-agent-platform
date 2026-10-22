import { Users } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Meetings" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Meeting assistant"
        title="Meetings"
        description="Turn a transcript into a summary, decisions and action items."
      />
      <EmptyState
        icon={Users}
        title="No meeting summaries yet"
        description="The meeting assistant arrives in Phase 5."
      />
    </div>
  );
}
