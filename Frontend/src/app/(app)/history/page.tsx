import { History } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "History" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Generations"
        title="History"
        description="Everything the agents produced for you."
      />
      <EmptyState
        icon={History}
        title="Nothing here yet"
        description="History arrives in Phase 5."
      />
    </div>
  );
}
