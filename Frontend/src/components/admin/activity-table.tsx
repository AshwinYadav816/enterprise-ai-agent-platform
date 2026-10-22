"use client";

import { Activity, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime, formatRelative } from "@/lib/format";
import {
  ACTION_LABEL,
  actionLabel,
  activityTarget,
  useActivity,
  useAdminUsers,
} from "@/lib/hooks/use-admin";
import { cn } from "@/lib/utils";

const ALL = "all";
/** Actions worth a second look are marked, never by colour alone. */
const NOTABLE = new Set(["auth.login_failed", "auth.refresh_token_reuse", "user.deactivated"]);

export function ActivityView() {
  const [action, setAction] = useState(ALL);
  const [userId, setUserId] = useState(ALL);
  const query = useActivity({
    action: action === ALL ? undefined : action,
    userId: userId === ALL ? undefined : userId,
  });
  // Names for the user filter and for "who was affected" (role changes, deactivations).
  const people = useAdminUsers({}, 100);
  const userNames = useMemo(
    () => new Map(people.users.map((u) => [u.id, u.full_name])),
    [people.users],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Activity"
        description="Sign-ins, account changes, uploads and generations in your organization."
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger className="w-full sm:w-60" aria-label="Filter by action">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All actions</SelectItem>
            {Object.entries(ACTION_LABEL).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={userId} onValueChange={setUserId}>
          <SelectTrigger className="w-full sm:w-60" aria-label="Filter by user">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Everyone</SelectItem>
            {people.users.map((u) => (
              <SelectItem key={u.id} value={u.id}>
                {u.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {query.isPending ? (
        <div className="space-y-2" aria-busy="true">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load activity"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : query.entries.length === 0 ? (
        <EmptyState
          icon={Activity}
          title="No activity matches"
          description="Try another action or person."
        />
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-lg border bg-card">
            <Table className="min-w-[760px]">
              <TableHeader className="bg-muted/60">
                <TableRow>
                  <TableHead className="pl-4">When</TableHead>
                  <TableHead>Who</TableHead>
                  <TableHead>What</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead className="pr-4">IP address</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.entries.map((entry) => {
                  const notable = NOTABLE.has(entry.action);
                  return (
                    <TableRow key={entry.id}>
                      <TableCell className="pl-4 whitespace-nowrap text-muted-foreground">
                        <time dateTime={entry.created_at} title={formatDateTime(entry.created_at)}>
                          {formatRelative(entry.created_at)}
                        </time>
                      </TableCell>
                      <TableCell className="max-w-56 truncate">
                        {entry.user_email ?? <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "whitespace-nowrap",
                          notable && "font-medium text-destructive",
                        )}
                      >
                        {notable && <span className="sr-only">Attention: </span>}
                        {actionLabel(entry.action)}
                      </TableCell>
                      <TableCell className="max-w-72 truncate text-muted-foreground">
                        {activityTarget(entry, userNames) || "—"}
                      </TableCell>
                      <TableCell className="pr-4 font-mono text-xs text-muted-foreground">
                        {entry.ip ?? "—"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
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
