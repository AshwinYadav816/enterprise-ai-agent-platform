"use client";

import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type ErrorStateProps = {
  /** The thrown value; its user-safe message is shown. */
  error?: unknown;
  title?: string;
  onRetry?: () => void;
  className?: string;
};

export function ErrorState({
  error,
  title = "Something went wrong",
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive-tint/40 px-6 py-12 text-center",
        className,
      )}
    >
      <AlertTriangle className="size-6 text-destructive" aria-hidden />
      <p className="type-title">{title}</p>
      {error !== undefined && (
        <p className="max-w-md text-muted-foreground">{errorMessage(error)}</p>
      )}
      {onRetry && (
        <Button variant="outline" onClick={onRetry} className="mt-1">
          <RotateCw /> Try again
        </Button>
      )}
    </div>
  );
}
