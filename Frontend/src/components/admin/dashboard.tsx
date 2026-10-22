"use client";

import { Coins, FileText, MessageSquare, MessagesSquare, RotateCw, Users } from "lucide-react";

import { AgentUsageChart } from "@/components/admin/agent-usage-chart";
import { formatCompact, formatCount } from "@/components/admin/chart-card";
import { DocsStatusChart } from "@/components/admin/docs-status-chart";
import { GenerationsChart } from "@/components/admin/generations-chart";
import { KpiTile } from "@/components/admin/kpi-tile";
import { TokensChart } from "@/components/admin/tokens-chart";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatBytes, formatDateTime, formatRelative } from "@/lib/format";
import { useAdminStats } from "@/lib/hooks/use-admin";

export function AdminDashboard() {
  const stats = useAdminStats();

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Admin"
        title="Dashboard"
        description="How your organization uses the platform."
        actions={
          stats.data && (
            <div className="flex items-center gap-2">
              <span
                className="type-small text-muted-foreground"
                title={formatDateTime(stats.data.generated_at)}
              >
                Updated {formatRelative(stats.data.generated_at)}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void stats.refetch()}
                disabled={stats.isFetching}
                aria-label="Refresh numbers"
              >
                <RotateCw className={stats.isFetching ? "animate-spin" : undefined} /> Refresh
              </Button>
            </div>
          )
        }
      />

      {stats.isPending ? (
        <DashboardSkeleton />
      ) : stats.isError ? (
        <ErrorState
          title="Couldn't load the numbers"
          error={stats.error}
          onRetry={() => void stats.refetch()}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
            <KpiTile
              label="Users"
              icon={Users}
              value={formatCount(stats.data.users.total)}
              detail={`${formatCount(stats.data.users.active_last_7_days)} active in the last 7 days`}
            />
            <KpiTile
              label="Documents"
              icon={FileText}
              value={formatCount(stats.data.documents.total)}
              detail={`${formatBytes(stats.data.documents.storage_bytes)} stored`}
            />
            <KpiTile
              label="Conversations"
              icon={MessagesSquare}
              value={formatCount(stats.data.conversations.total)}
            />
            <KpiTile
              label="Messages"
              icon={MessageSquare}
              value={formatCount(stats.data.messages.total)}
            />
            <KpiTile
              label="Tokens"
              icon={Coins}
              value={formatCompact(stats.data.tokens.last_30_days_total)}
              detail="Last 30 days"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <TokensChart tokens={stats.data.tokens} />
            <AgentUsageChart perAgent={stats.data.tokens.per_agent} />
            <DocsStatusChart documents={stats.data.documents} />
            <GenerationsChart generations={stats.data.generations} />
          </div>
          <p className="type-small text-muted-foreground">
            Numbers can be up to a minute old; use Refresh for the latest. Users by role:{" "}
            {Object.entries(stats.data.users.by_role)
              .map(([role, n]) => `${n} ${role}${n === 1 ? "" : "s"}`)
              .join(", ")}
            {stats.data.users.deactivated ? `; ${stats.data.users.deactivated} deactivated` : ""}.
          </p>
        </>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <span className="sr-only" role="status">
        Loading dashboard…
      </span>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-80" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    </div>
  );
}
