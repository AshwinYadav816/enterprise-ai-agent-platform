"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { HOME_PATH, loginPath, postLoginPath } from "@/lib/redirects";
import { useAuth } from "@/providers/auth-provider";

type AuthGuardProps = {
  children: React.ReactNode;
  /** Non-admins are sent to /chat. */
  adminOnly?: boolean;
  /** Render even when the user still has to change a temporary password (the change page). */
  allowPasswordChange?: boolean;
  /** Shown while deciding; defaults to a full-page skeleton. */
  fallback?: React.ReactNode;
};

/**
 * Client-side route protection (the backend enforces auth anyway). Renders children only for an
 * authenticated user who may see the page; otherwise shows the fallback and redirects:
 * anonymous → /login?next=<path>, temporary password → /change-password, non-admin → /chat.
 */
export function AuthGuard(props: AuthGuardProps) {
  const fallback = props.fallback ?? <FullPageSkeleton />;
  return (
    <Suspense fallback={fallback}>
      <AuthGuardInner {...props} fallback={fallback} />
    </Suspense>
  );
}

function AuthGuardInner({ children, adminOnly, allowPasswordChange, fallback }: AuthGuardProps) {
  const { user, status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const here = search ? `${pathname}?${search}` : pathname;

  let redirect: string | null = null;
  if (status === "anonymous") redirect = loginPath(here);
  else if (user?.must_change_password && !allowPasswordChange) redirect = postLoginPath(user, here);
  else if (adminOnly && user && user.role !== "admin") redirect = HOME_PATH;

  useEffect(() => {
    if (redirect) router.replace(redirect);
  }, [redirect, router]);

  if (status !== "authenticated" || redirect) return fallback;
  return children;
}

/** For /login and /register: signed-in users go to `?next=` (or /chat, or the password change). */
export function GuestGuard({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<FormSkeleton />}>
      <GuestGuardInner>{children}</GuestGuardInner>
    </Suspense>
  );
}

function GuestGuardInner({ children }: { children: React.ReactNode }) {
  const { user, status } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const redirect = status === "authenticated" && user ? postLoginPath(user, next) : null;

  useEffect(() => {
    if (redirect) router.replace(redirect);
  }, [redirect, router]);

  if (status === "loading" || redirect) return <FormSkeleton />;
  return children;
}

/** Shell-shaped placeholder while the session is restored (no flash of the login page). */
export function FullPageSkeleton() {
  return (
    <div className="flex min-h-svh w-full" aria-busy="true">
      <span className="sr-only" role="status">
        Loading…
      </span>
      <div className="hidden w-64 shrink-0 flex-col gap-3 border-r bg-sidebar p-4 lg:flex">
        <Skeleton className="mb-4 h-7 w-36" />
        <Skeleton className="h-9 w-full" />
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>
      <div className="flex-1 space-y-6 px-4 py-8 md:px-8">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-9 w-72 max-w-full" />
        <Skeleton className="h-40 w-full max-w-3xl" />
      </div>
    </div>
  );
}

export function ContentSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true">
      <span className="sr-only" role="status">
        Loading…
      </span>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-9 w-72 max-w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <span className="sr-only" role="status">
        Loading…
      </span>
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
    </div>
  );
}
