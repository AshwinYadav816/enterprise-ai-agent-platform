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

const KINDS = [
  { key: "meeting", label: "Meetings", color: "var(--chart-1)" },
  { key: "report", label: "Reports", color: "var(--chart-3)" },
  { key: "email", label: "Emails", color: "var(--chart-4)" },
  { key: "document_insights", label: "Insights", color: "var(--chart-5)" },
] as const;

const config = { count: { label: "Generated" } } satisfies ChartConfig;

/** What the tools produced (all time), by kind. */
export function GenerationsChart({ generations }: { generations: AdminStats["generations"] }) {
  const data = KINDS.map((k) => ({ ...k, count: generations.by_kind[k.key] ?? 0 }));
  const top = [...data].sort((a, b) => b.count - a.count)[0];
  const takeaway =
    generations.total === 0
      ? "Nothing generated with the tools yet."
      : `${formatCount(generations.total)} generated in total; most often ${top.label.toLowerCase()} (${formatCount(top.count)}).`;

  return (
    <ChartCard
      title="Generations by kind"
      takeaway={takeaway}
      table={{ columns: ["Kind", "Generated"], rows: data.map((d) => [d.label, d.count]) }}
    >
      {generations.total === 0 ? (
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
