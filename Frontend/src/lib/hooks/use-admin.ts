"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import type { components } from "@/lib/api/schema";

export type AdminStats = components["schemas"]["AdminStats"];
export type AdminUser = components["schemas"]["UserOut"];
export type AuditEntry = components["schemas"]["AuditLogOut"];
export type UserRole = components["schemas"]["UserRole"];
export type CreateUserRequest = components["schemas"]["CreateUserRequest"];
export type CreatedUser = components["schemas"]["CreatedUserResponse"];

/** Dashboard numbers: one call; the backend caches them for 60 s. */
export function useAdminStats() {
  return useQuery({
    queryKey: keys.admin.stats(),
    queryFn: async () => unwrap(await api.GET("/api/v1/admin/stats")),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export type UserFilters = { search?: string; role?: UserRole };

export function useAdminUsers({ search, role }: UserFilters, limit = 20) {
  const query = useInfiniteQuery({
    queryKey: keys.admin.users({ search, role, limit }),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/admin/users", {
          params: { query: { search: search || undefined, role, cursor: pageParam, limit } },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const users = useMemo(() => query.data?.pages.flatMap((page) => page.items) ?? [], [query.data]);
  return { ...query, users };
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: CreateUserRequest) =>
      unwrap(await api.POST("/api/v1/admin/users", { body })),
    meta: { silentError: true }, // shown in the dialog (e.g. email already taken)
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.admin.all }),
  });
}

/** Role change or (de)activation. Guard errors (last admin, yourself) toast globally. */
export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...body }: { id: string; role?: UserRole; is_active?: boolean }) =>
      unwrap(
        await api.PATCH("/api/v1/admin/users/{user_id}", {
          params: { path: { user_id: id } },
          body,
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.admin.all }),
  });
}

export type ActivityFilters = { action?: string; userId?: string };

export function useActivity({ action, userId }: ActivityFilters) {
  const query = useInfiniteQuery({
    queryKey: keys.admin.activity({ action, userId }),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/admin/activity", {
          params: { query: { action, user_id: userId, cursor: pageParam, limit: 30 } },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const entries = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );
  return { ...query, entries };
}

// ---- display helpers

export const ROLE_LABEL: Record<UserRole, string> = {
  admin: "Admin",
  manager: "Manager",
  employee: "Employee",
};

/** Stable audit action strings (Backend app/services/audit.py) → readable labels. */
export const ACTION_LABEL: Record<string, string> = {
  "auth.register": "Created the workspace",
  "auth.login": "Signed in",
  "auth.login_failed": "Failed sign-in",
  "auth.refresh_token_reuse": "Suspicious session reuse",
  "user.password_changed": "Changed password",
  "user.created": "Added a user",
  "user.role_changed": "Changed a role",
  "user.deactivated": "Deactivated a user",
  "user.reactivated": "Reactivated a user",
  "document.uploaded": "Uploaded a document",
  "document.deleted": "Deleted a document",
  "conversation.deleted": "Deleted a conversation",
  "generation.created": "Generated content",
};

export const actionLabel = (action: string) => ACTION_LABEL[action] ?? action;

const KIND_LABEL: Record<string, string> = {
  meeting: "meeting summary",
  report: "report",
  email: "email",
  document_insights: "document insights",
};

/** What an audit entry was about, in words ("leave-policy.pdf", "Mina → manager"…). */
export function activityTarget(entry: AuditEntry, userNames: Map<string, string>): string {
  const meta = (entry.meta ?? {}) as Record<string, unknown>;
  const str = (key: string) => (typeof meta[key] === "string" ? (meta[key] as string) : "");
  const targetUser = entry.target_id ? userNames.get(entry.target_id) : undefined;
  switch (entry.action) {
    case "document.uploaded":
    case "document.deleted":
      return str("filename");
    case "user.created":
      return [str("email"), str("role") && `as ${str("role")}`].filter(Boolean).join(" ");
    case "user.role_changed":
      return `${targetUser ?? "a user"}: ${str("from")} → ${str("to")}`;
    case "user.deactivated":
    case "user.reactivated":
      return targetUser ?? "a user";
    case "generation.created":
      return KIND_LABEL[str("kind")] ?? str("kind");
    case "auth.login_failed":
      return str("email");
    case "auth.register":
      return str("org_name");
    case "auth.refresh_token_reuse":
      return "all sessions signed out";
    default:
      return "";
  }
}
