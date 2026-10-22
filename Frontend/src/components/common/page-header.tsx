import { cn } from "@/lib/utils";

type PageHeaderProps = {
  title: string;
  eyebrow?: string;
  description?: React.ReactNode;
  /** Buttons on the right (wrap below the title on small screens). */
  actions?: React.ReactNode;
  className?: string;
};

export function PageHeader({ title, eyebrow, description, actions, className }: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0 space-y-1.5">
        {eyebrow && <p className="type-eyebrow text-muted-foreground">{eyebrow}</p>}
        <h1 className="type-display text-balance">{title}</h1>
        {description && <p className="max-w-2xl text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
