"use client";

import { Loader2, type LucideIcon } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { GenerationView } from "@/components/tools/generation-view";
import { Skeleton } from "@/components/ui/skeleton";
import type { Generation } from "@/lib/hooks/use-tools";

type ToolLayoutProps = {
  eyebrow: string;
  title: string;
  description: string;
  form: React.ReactNode;
  /** The latest run of this tool. */
  run: { isPending: boolean; error: unknown; data: Generation | undefined };
  empty: { icon: LucideIcon; title: string; description: string };
};

/** Form left (~40 %), result right on desktop; stacked on phones. */
export function ToolLayout({ eyebrow, title, description, form, run, empty }: ToolLayoutProps) {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <section aria-label="Input" className="rounded-lg border bg-card p-5 lg:sticky lg:top-6">
          {form}
        </section>
        <section aria-label="Result" aria-live="polite" className="min-w-0">
          {run.isPending ? (
            <Working />
          ) : run.error ? (
            <ErrorState title="That didn't work" error={run.error} />
          ) : run.data ? (
            <GenerationView generation={run.data} showHistoryLink />
          ) : (
            <EmptyState icon={empty.icon} title={empty.title} description={empty.description} />
          )}
        </section>
      </div>
    </div>
  );
}

function Working() {
  return (
    <div className="space-y-4 rounded-lg border bg-card p-5" aria-busy="true">
      <p className="flex items-center gap-2 text-muted-foreground" role="status">
        <Loader2 className="size-4 animate-spin text-primary" aria-hidden />
        Working on it… this can take up to a minute.
      </p>
      <Skeleton className="h-6 w-2/3" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-11/12" />
        <Skeleton className="h-4 w-4/5" />
      </div>
      <Skeleton className="h-24 w-full" />
    </div>
  );
}

/** Submit button label with a spinner while the request runs. */
export function SubmitLabel({
  pending,
  idle,
  busy,
}: {
  pending: boolean;
  idle: string;
  busy: string;
}) {
  return (
    <>
      {pending && <Loader2 className="animate-spin" aria-hidden />}
      {pending ? busy : idle}
    </>
  );
}
