"use client";

import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartCard, formatCompact, formatCount } from "@/components/admin/chart-card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { AdminStats } from "@/lib/hooks/use-admin";

const config = {
  total_tokens: { label: "Tokens", color: "var(--chart-1)" },
} satisfies ChartConfig;

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

/** Tokens per day for the last 30 days (UTC days); today's point in coral. */
export function TokensChart({ tokens }: { tokens: AdminStats["tokens"] }) {
  const data = tokens.per_day.map((d) => ({ ...d, label: day.format(new Date(d.date)) }));
  const busiest = data.reduce((max, d) => (d.total_tokens > max.total_tokens ? d : max), data[0]);
  const takeaway =
    tokens.last_30_days_total === 0
      ? "No AI usage in the last 30 days yet."
      : `${formatCount(tokens.last_30_days_total)} tokens in 30 days; busiest day ${busiest.label} (${formatCount(busiest.total_tokens)}).`;

  return (
    <ChartCard
      title="Tokens per day"
      takeaway={takeaway}
      className="lg:col-span-2"
      table={{
        columns: ["Day (UTC)", "Prompt tokens", "Completion tokens", "Total"],
        rows: data.map((d) => [d.label, d.prompt_tokens, d.completion_tokens, d.total_tokens]),
      }}
    >
      <ChartContainer config={config} className="aspect-auto h-60 w-full">
        <AreaChart data={data} margin={{ left: 0, right: 12, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={false}
            interval="preserveStartEnd"
            minTickGap={24}
            tick={{ fill: "var(--chart-axis)" }}
          />
          <YAxis
            width={44}
            tickLine={false}
            axisLine={false}
            allowDecimals={false}
            tickFormatter={formatCompact}
            tick={{ fill: "var(--chart-axis)" }}
          />
          <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
          <Area
            dataKey="total_tokens"
            type="monotone"
            stroke="var(--color-total_tokens)"
            strokeWidth={2}
            fill="var(--color-total_tokens)"
            fillOpacity={0.12}
            isAnimationActive={false}
            dot={(props: { cx?: number; cy?: number; index?: number }) =>
              props.index === data.length - 1 && props.cx != null && props.cy != null ? (
                // today: the coral signature point
                <circle
                  key="today"
                  cx={props.cx}
                  cy={props.cy}
                  r={4.5}
                  fill="var(--coral)"
                  stroke="var(--card)"
                  strokeWidth={2}
                />
              ) : (
                <g key={props.index} />
              )
            }
          />
        </AreaChart>
      </ChartContainer>
      <p className="mt-2 type-small text-muted-foreground">
        Days are in UTC.{" "}
        <span className="mx-1 inline-block size-2 rounded-full bg-coral align-middle" aria-hidden />{" "}
        Today
      </p>
    </ChartCard>
  );
}
