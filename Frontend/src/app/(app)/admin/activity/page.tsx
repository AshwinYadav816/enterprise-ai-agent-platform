import { Activity } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Activity" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Admin" title="Activity" description="Who did what, and when." />
      <EmptyState
        icon={Activity}
        title="Activity log coming soon"
        description="Arrives in Phase 6."
      />
    </div>
  );
}
