"use client";

import { Loader2, Search, UserCheck, UserX, Users } from "lucide-react";
import { useState } from "react";

import { CreateUserDialog } from "@/components/admin/create-user-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  ROLE_LABEL,
  useAdminUsers,
  useUpdateUser,
  type AdminUser,
  type UserRole,
} from "@/lib/hooks/use-admin";
import { useUrlSearch, useUrlState } from "@/lib/hooks/use-url-state";
import { useAuth } from "@/providers/auth-provider";

const ROLES = Object.keys(ROLE_LABEL) as UserRole[];

export function UsersView() {
  const { user: me } = useAuth();
  const { text: searchText, setText: setSearchText, search } = useUrlSearch();
  const [role, setRole] = useUrlState<UserRole | "all">("role", "all", ["all", ...ROLES]);
  const [toToggle, setToToggle] = useState<AdminUser | null>(null);
  const update = useUpdateUser();

  const query = useAdminUsers({ search, role: role === "all" ? undefined : role });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Admin"
        title="Users"
        description="Add people, set their role, and deactivate accounts that shouldn't sign in."
        actions={<CreateUserDialog />}
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by name or email"
            aria-label="Search users"
            className="pl-9"
          />
        </div>
        <Select value={role} onValueChange={(v) => setRole(v as UserRole | "all")}>
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by role">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r}>
                {ROLE_LABEL[r]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {query.isPending ? (
        <div className="space-y-2" aria-busy="true">
          {Array.from({ length: 5 }, (_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load users"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : query.users.length === 0 ? (
        <EmptyState
          icon={Users}
          title="No users match"
          description="Try another name, email or role."
        />
      ) : (
        <div className="space-y-4">
          <div className="overflow-x-auto rounded-lg border bg-card">
            <Table className="min-w-[720px]">
              <TableHeader className="bg-muted/60">
                <TableRow>
                  <TableHead className="pl-4">Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead className="w-40">Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last sign-in</TableHead>
                  <TableHead className="pr-4 text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.users.map((u) => {
                  const self = u.id === me?.id;
                  return (
                    <TableRow key={u.id}>
                      <TableCell className="pl-4 font-medium">
                        {u.full_name}
                        {self && <span className="ml-1.5 text-muted-foreground">(you)</span>}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{u.email}</TableCell>
                      <TableCell>
                        <Select
                          value={u.role}
                          disabled={self || update.isPending}
                          onValueChange={(next) =>
                            update.mutate({ id: u.id, role: next as UserRole })
                          }
                        >
                          <SelectTrigger
                            size="sm"
                            className="w-36"
                            aria-label={`Role of ${u.full_name}`}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ROLES.map((r) => (
                              <SelectItem key={r} value={r}>
                                {ROLE_LABEL[r]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {u.is_active ? (
                            <Badge variant="success">Active</Badge>
                          ) : (
                            <Badge variant="destructive">Deactivated</Badge>
                          )}
                          {u.is_active && u.must_change_password && (
                            <Badge variant="warning">Temporary password</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {u.last_login_at ? (
                          <time dateTime={u.last_login_at} title={formatDateTime(u.last_login_at)}>
                            {formatRelative(u.last_login_at)}
                          </time>
                        ) : (
                          "Never"
                        )}
                      </TableCell>
                      <TableCell className="pr-4 text-right">
                        {!self && (
                          <Button variant="ghost" size="sm" onClick={() => setToToggle(u)}>
                            {u.is_active ? <UserX /> : <UserCheck />}
                            {u.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        )}
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

      <AlertDialog open={toToggle !== null} onOpenChange={(open) => !open && setToToggle(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {toToggle?.is_active
                ? `Deactivate ${toToggle.full_name}?`
                : `Activate ${toToggle?.full_name}?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {toToggle?.is_active
                ? "They are signed out everywhere and can't sign in until reactivated. Their documents stay."
                : "They can sign in again with their current password."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant={toToggle?.is_active ? "destructive" : "default"}
              disabled={update.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (!toToggle) return;
                update.mutate(
                  { id: toToggle.id, is_active: !toToggle.is_active },
                  { onSettled: () => setToToggle(null) },
                );
              }}
            >
              {toToggle?.is_active ? "Deactivate" : "Activate"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
