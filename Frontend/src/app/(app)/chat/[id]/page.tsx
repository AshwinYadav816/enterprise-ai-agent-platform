"use client";

import { useParams } from "next/navigation";

import { EmptyState } from "@/components/common/empty-state";
import { PageHeader } from "@/components/common/page-header";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Chat" title="Conversation" />
      <EmptyState
        title="Coming soon"
        description={<span className="font-mono text-xs">{id}</span>}
      />
    </div>
  );
}
