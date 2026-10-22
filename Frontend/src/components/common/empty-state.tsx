import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  title: string;
  description?: React.ReactNode;
  icon?: LucideIcon;
  /** Usually one primary button. */
  action?: React.ReactNode;
  className?: string;
};

/** Illustration-free empty state: a serif line, a short hint and one action. */
export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed px-6 py-14 text-center",
        className,
      )}
    >
      {Icon && (
        <span className="flex size-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <Icon className="size-5" aria-hidden />
        </span>
      )}
      <p className="max-w-md type-title text-balance">{title}</p>
      {description && <p className="max-w-md text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
