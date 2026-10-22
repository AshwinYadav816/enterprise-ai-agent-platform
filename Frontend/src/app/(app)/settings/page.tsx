import { Settings } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Account" title="Settings" description="Your profile and password." />
      <EmptyState
        icon={Settings}
        title="Settings are on the way"
        description="Profile settings arrive in Phase 7."
      />
    </div>
  );
}
