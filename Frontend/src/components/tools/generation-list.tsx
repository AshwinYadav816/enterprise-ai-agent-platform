"use client";

import { ChevronRight, FileSearch, History, Loader2, Mail, NotebookPen, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatDateTime, formatRelative } from "@/lib/format";
import { KIND_LABEL, useGenerations, type GenerationKind } from "@/lib/hooks/use-tools";

const FILTERS: { value: GenerationKind | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "meeting", label: "Meetings" },
  { value: "report", label: "Reports" },
  { value: "email", label: "Emails" },
  { value: "document_insights", label: "Insights" },
];

export const KIND_ICON = {
  meeting: Users,
  report: NotebookPen,
  email: Mail,
  document_insights: FileSearch,
} as const;

/** Everything the tools produced for you, newest first. */
export function GenerationList() {
  const [kind, setKind] = useState<GenerationKind | "all">("all");
  const query = useGenerations(kind === "all" ? undefined : kind);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Generations"
        title="History"
        description="Every meeting summary, report, email and document insight you've generated."
      />

      <Tabs value={kind} onValueChange={(v) => setKind(v as GenerationKind | "all")}>
        <TabsList aria-label="Filter by kind" className="max-w-full justify-start overflow-x-auto">
          {FILTERS.map((f) => (
            <TabsTrigger key={f.value} value={f.value} className="flex-none px-3">
              {f.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {query.isPending ? (
        <div className="space-y-2" aria-busy="true">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load your history"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : query.generations.length === 0 ? (
        <EmptyState
          icon={History}
          title={
            kind === "all"
              ? "Nothing here yet"
              : `No ${FILTERS.find((f) => f.value === kind)?.label.toLowerCase()} yet`
          }
          description="Summaries, reports, emails and insights you create are saved here."
          action={
            <Button asChild variant="outline">
              <Link href="/meetings">Summarize a meeting</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          <ul className="divide-y overflow-hidden rounded-lg border bg-card">
            {query.generations.map((g) => {
              const Icon = KIND_ICON[g.kind];
              return (
                <li key={g.id}>
                  <Link
                    href={`/history/${g.id}`}
                    className="flex items-center gap-4 px-4 py-3 transition-colors duration-150 hover:bg-accent focus-visible:bg-accent"
                  >
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                      <Icon className="size-4" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{g.title}</span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-2 type-small text-muted-foreground">
                        <Badge variant="secondary">{KIND_LABEL[g.kind]}</Badge>
                        <time dateTime={g.created_at} title={formatDateTime(g.created_at)}>
                          {formatRelative(g.created_at)}
                        </time>
                      </span>
                    </span>
                    <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                  </Link>
                </li>
              );
            })}
          </ul>
          {query.hasNextPage && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                onClick={() => void query.fetchNextPage()}
                disabled={query.isFetchingNextPage}
              >
                {query.isFetchingNextPage && <Loader2 className="animate-spin" aria-hidden />}
                Load more
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
