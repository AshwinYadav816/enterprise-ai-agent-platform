import { FileText } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Documents" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Knowledge base"
        title="Documents"
        description="Upload files your team can ask questions about."
      />
      <EmptyState
        icon={FileText}
        title="Your knowledge base is empty"
        description="Uploading arrives in Phase 3."
      />
    </div>
  );
}
