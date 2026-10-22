"use client";

import { useEffect } from "react";

import { ErrorState } from "@/components/common/error-state";

/** Something on an app page crashed: keep the shell and offer a retry (Next 16 `retry()`). */
export default function AppError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return <ErrorState title="This page hit a problem" onRetry={retry} className="mt-6" />;
}
