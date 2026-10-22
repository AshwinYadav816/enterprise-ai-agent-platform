import { Mail } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export const metadata: Metadata = { title: "Email" };

export default function Page() {
  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Email assistant"
        title="Email"
        description="Draft, rewrite and tidy up emails in the right tone."
      />
      <EmptyState
        icon={Mail}
        title="No emails yet"
        description="The email assistant arrives in Phase 5."
      />
    </div>
  );
}
