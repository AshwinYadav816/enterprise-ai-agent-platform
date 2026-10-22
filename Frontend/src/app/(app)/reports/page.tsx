import { NotebookPen } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Report generator"
        title="Reports"
        description="Weekly, monthly, sprint and project reports from your documents."
      />
      <EmptyState
        icon={NotebookPen}
        title="No reports yet"
        description="The report generator arrives in Phase 5."
      />
    </div>
  );
}
