"use client";

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartCard, formatCompact, formatCount } from "@/components/admin/chart-card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { agentLabel } from "@/lib/chat/types";
import type { AdminStats } from "@/lib/hooks/use-admin";

const config = { tokens: { label: "Tokens", color: "var(--chart-1)" } } satisfies ChartConfig;

/** Which agents use the tokens (last 30 days), as horizontal bars. */
export function AgentUsageChart({ perAgent }: { perAgent: AdminStats["tokens"]["per_agent"] }) {
  const data = perAgent.map((a) => ({ ...a, label: agentLabel(a.agent) }));
  const top = data[0];
  const takeaway = top
    ? `${top.label} used the most tokens: ${formatCount(top.tokens)} across ${formatCount(top.requests)} ${top.requests === 1 ? "request" : "requests"}.`
    : "No agent has been used in the last 30 days.";

  return (
    <ChartCard
      title="Usage per agent"
      takeaway={takeaway}
      table={{
        columns: ["Agent", "Requests", "Tokens"],
        rows: data.map((a) => [a.label, a.requests, a.tokens]),
      }}
    >
      {data.length === 0 ? (
        <EmptyChart />
      ) : (
        <ChartContainer
          config={config}
          className="aspect-auto w-full"
          style={{ height: 40 + data.length * 36 }}
        >
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 16 }}>
            <CartesianGrid horizontal={false} stroke="var(--chart-grid)" />
            <XAxis
              type="number"
              tickLine={false}
              axisLine={false}
              tickFormatter={formatCompact}
              tick={{ fill: "var(--chart-axis)" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={80}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--foreground)" }}
            />
            <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
            <Bar
              dataKey="tokens"
              fill="var(--color-tokens)"
              radius={4}
              barSize={18}
              isAnimationActive={false}
            />
          </BarChart>
        </ChartContainer>
      )}
    </ChartCard>
  );
}

export function EmptyChart() {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground">
      Nothing to show yet
    </div>
  );
}
