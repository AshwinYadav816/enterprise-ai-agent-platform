import { LayoutDashboard } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Admin" title="Dashboard" description="Usage across your organization." />
      <EmptyState
        icon={LayoutDashboard}
        title="Dashboard coming soon"
        description="Charts and KPIs arrive in Phase 6."
      />
    </div>
  );
}
