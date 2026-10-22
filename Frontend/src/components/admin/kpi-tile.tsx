import type { LucideIcon } from "lucide-react";

export function KpiTile({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail?: string;
  icon: LucideIcon;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="type-eyebrow text-muted-foreground">{label}</p>
        <Icon className="size-4 text-muted-foreground" aria-hidden />
      </div>
      <p className="mt-2 font-serif text-3xl leading-none font-semibold tabular-nums">{value}</p>
      {detail && <p className="mt-2 type-small text-muted-foreground">{detail}</p>}
    </div>
  );
}
