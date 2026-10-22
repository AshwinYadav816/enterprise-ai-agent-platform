"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { GenerationView } from "@/components/tools/generation-view";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/errors";
import { KIND_LABEL, useGeneration, type Generation } from "@/lib/hooks/use-tools";

/** /history/[id]: one saved generation, with what it was made from. */
export function GenerationDetail() {
  const { id } = useParams<{ id: string }>();
  const query = useGeneration(id);

  const back = (
    <Button asChild variant="ghost" size="sm" className="-ml-2">
      <Link href="/history">
        <ArrowLeft /> History
      </Link>
    </Button>
  );

  if (query.isPending) {
    return (
      <div className="space-y-6" aria-busy="true">
        {back}
        <Skeleton className="h-9 w-80 max-w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <div className="space-y-6">
        {back}
        <ErrorState
          title={missing ? "This item doesn't exist" : "Couldn't load this item"}
          error={query.error}
          onRetry={missing ? undefined : () => void query.refetch()}
        />
      </div>
    );
  }

  const generation = query.data;
  return (
    <div className="space-y-6">
      {back}
      <PageHeader eyebrow={KIND_LABEL[generation.kind]} title={generation.title} />
      <InputSummary generation={generation} />
      <div className="max-w-3xl">
        <GenerationView generation={generation} showHeader={false} />
      </div>
    </div>
  );
}

const EMAIL_TASK: Record<string, string> = {
  draft: "Draft",
  rewrite: "Rewrite",
  grammar: "Fix grammar",
  tone: "Change tone",
  summarize_thread: "Summarize thread",
};

/** A one-line reminder of the request (type, period, task, tone…). */
function InputSummary({ generation }: { generation: Generation }) {
  const input = generation.input as Record<string, unknown>;
  const text = (key: string) => (typeof input[key] === "string" ? (input[key] as string) : "");
  const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const parts: string[] = [];
  if (generation.kind === "report") {
    parts.push(text("report_type") && capital(`${text("report_type")} report`), text("period"));
  } else if (generation.kind === "email") {
    parts.push(EMAIL_TASK[text("task")] ?? text("task"), text("tone") && `${text("tone")} tone`);
  } else if (generation.kind === "document_insights") {
    parts.push(text("filename")); // a file name: shown exactly as uploaded
  } else if (typeof input.transcript_chars === "number") {
    parts.push(`From a ${input.transcript_chars.toLocaleString()}-character transcript`);
  }
  const line = parts.filter(Boolean).join(" · ");
  if (!line) return null;
  return <p className="-mt-3 type-small text-muted-foreground">{line}</p>;
}
