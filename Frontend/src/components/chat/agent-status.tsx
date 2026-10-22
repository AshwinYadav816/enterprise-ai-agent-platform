import { Fragment } from "react";

import type { Step } from "@/lib/chat/stream-store";
import { agentLabel } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

type AgentStatusProps =
  | { live: true; planning: boolean; steps: Step[]; statusLine: string | null }
  | { live: false; agents: string[] };

/**
 * Live: "Planning… → Meeting agent → Email agent" with the active step in blue and a coral pulsing
 * dot, plus the latest progress line. Saved: a quiet "Used: Meeting, Email".
 */
export function AgentStatus(props: AgentStatusProps) {
  if (!props.live) {
    const agents = props.agents.filter((a) => a && a !== "chat");
    if (agents.length === 0) return null;
    return (
      <p className="mb-2 font-sans type-small text-muted-foreground">
        Used: {agents.map(agentLabel).join(", ")}
      </p>
    );
  }

  const { planning, steps, statusLine } = props;
  return (
    <div className="mb-3 space-y-1 font-sans" role="status" aria-live="polite">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 type-small text-muted-foreground">
        <StepLabel active={planning}>Planning…</StepLabel>
        {steps.map((step, i) => (
          <Fragment key={`${step.agent}-${i}`}>
            <span aria-hidden>→</span>
            <StepLabel active={step.status === "active"} failed={step.status === "failed"}>
              {agentLabel(step.agent)} agent
            </StepLabel>
          </Fragment>
        ))}
      </p>
      {statusLine && <p className="pl-3 type-small text-muted-foreground italic">{statusLine}</p>}
    </div>
  );
}

function StepLabel({
  active,
  failed,
  children,
}: {
  active: boolean;
  failed?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5",
        active && "font-medium text-primary",
        failed && "text-destructive line-through",
      )}
    >
      {active && <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-coral" />}
      {children}
    </span>
  );
}
