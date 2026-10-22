"use client";

import { Bot } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { agentLabel, FORCEABLE_AGENTS, type AgentName } from "@/lib/chat/types";

export type AgentChoice = AgentName | "auto";

/** Auto lets the router plan; otherwise one agent handles the message. */
export function AgentSelect({
  value,
  onChange,
  disabled,
}: {
  value: AgentChoice;
  onChange: (value: AgentChoice) => void;
  disabled?: boolean;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as AgentChoice)} disabled={disabled}>
      <SelectTrigger
        size="sm"
        aria-label="Agent"
        className="h-8 w-auto gap-1.5 border-transparent bg-transparent shadow-none hover:bg-accent"
      >
        <Bot className="text-muted-foreground" aria-hidden />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="start">
        <SelectItem value="auto">Auto</SelectItem>
        {FORCEABLE_AGENTS.map((agent) => (
          <SelectItem key={agent} value={agent}>
            {agentLabel(agent)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
