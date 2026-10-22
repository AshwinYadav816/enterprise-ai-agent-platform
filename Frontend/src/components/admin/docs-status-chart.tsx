"use client";

import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from "recharts";

import { EmptyChart } from "@/components/admin/agent-usage-chart";
import { ChartCard, formatCount } from "@/components/admin/chart-card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { AdminStats } from "@/lib/hooks/use-admin";

const STATUS = [
  { key: "ready", label: "Ready", color: "var(--success)" },
  { key: "processing", label: "Processing", color: "var(--warning)" },
  { key: "failed", label: "Failed", color: "var(--destructive)" },
] as const;

const config = { count: { label: "Documents" } } satisfies ChartConfig;

/** Documents by status, in the status colours used everywhere else. */
export function DocsStatusChart({ documents }: { documents: AdminStats["documents"] }) {
  const data = STATUS.map((s) => ({ ...s, count: documents.by_status[s.key] ?? 0 }));
  const ready = documents.by_status.ready ?? 0;
  const failed = documents.by_status.failed ?? 0;
  const takeaway =
    documents.total === 0
      ? "No documents uploaded yet."
      : `${formatCount(ready)} of ${formatCount(documents.total)} documents are ready${failed ? `; ${formatCount(failed)} failed` : ""}.`;

  return (
    <ChartCard
      title="Documents by status"
      takeaway={takeaway}
      table={{ columns: ["Status", "Documents"], rows: data.map((d) => [d.label, d.count]) }}
    >
      {documents.total === 0 ? (
        <EmptyChart />
      ) : (
        <ChartContainer config={config} className="aspect-auto h-48 w-full">
          <BarChart data={data} margin={{ left: 0, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--chart-axis)" }}
            />
            <YAxis
              width={32}
              allowDecimals={false}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--chart-axis)" }}
            />
            <ChartTooltip cursor={false} content={<ChartTooltipContent hideIndicator />} />
            <Bar dataKey="count" radius={4} barSize={40} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.key} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ChartContainer>
      )}
    </ChartCard>
  );
}
