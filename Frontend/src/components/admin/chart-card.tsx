import { cn } from "@/lib/utils";

/**
 * A chart with its title, a one-line takeaway, and the same numbers as a visually hidden table
 * for screen readers (charts are images to them).
 */
export function ChartCard({
  title,
  takeaway,
  table,
  children,
  className,
}: {
  title: string;
  takeaway: string;
  table: { columns: string[]; rows: (string | number)[][] };
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-lg border bg-card p-5", className)}>
      <h2 className="type-title text-lg">{title}</h2>
      <p className="mt-1 type-small text-muted-foreground">{takeaway}</p>
      <div className="mt-4" aria-hidden>
        {children}
      </div>
      <table className="sr-only">
        <caption>{title}</caption>
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c} scope="col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export const formatCount = (n: number) => n.toLocaleString("en-US");
export const formatCompact = (n: number) =>
  new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
