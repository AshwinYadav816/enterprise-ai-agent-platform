import { UserCog } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Users" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Invite people and manage their roles."
      />
      <EmptyState
        icon={UserCog}
        title="User management coming soon"
        description="Arrives in Phase 6."
      />
    </div>
  );
}
