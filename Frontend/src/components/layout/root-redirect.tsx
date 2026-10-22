"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { FullPageSkeleton } from "@/components/layout/auth-guard";
import { postLoginPath } from "@/lib/redirects";
import { useAuth } from "@/providers/auth-provider";

/** "/" → the app for a signed-in user, else /login (Phase 7 replaces this with a landing page). */
export function RootRedirect() {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anonymous") router.replace("/login");
    else if (status === "authenticated" && user) router.replace(postLoginPath(user));
  }, [status, user, router]);

  return <FullPageSkeleton />;
}
