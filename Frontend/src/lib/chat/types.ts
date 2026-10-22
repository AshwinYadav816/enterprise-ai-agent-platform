import type { components } from "@/lib/api/schema";

export type Conversation = components["schemas"]["ConversationOut"];
export type Message = components["schemas"]["MessageOut"];
export type SendMessageBody = components["schemas"]["SendMessageRequest"];
export type AgentName = components["schemas"]["AgentName"];

// ---- SSE event data (shapes from ai/src/eap_ai: agents/base.py, orchestrator/graph.py)

export type Source = {
  n: number;
  doc_id: string;
  filename: string;
  page?: number | null;
  snippet: string;
};

export type ResultData = {
  agent: string;
  output: Record<string, unknown>;
  /** meeting and report results: ready for the PDF export */
  markdown?: string;
  [extra: string]: unknown;
};

export type StatusData = { message: string };
export type AgentData = { name: string; step: number; total: number; instruction?: string };
export type ErrorData = { message: string; agent?: string };
export type DoneData = {
  answer: string;
  agents: string[];
  errors: number;
  message_id: string | null;
  usage?: Record<string, unknown>;
};

// ---- agent result outputs

export type ActionItem = { task: string; owner: string; due_date?: string | null };
export type MeetingOutput = {
  summary: string;
  key_decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
};
export type EmailOutput = { subject: string; body: string; notes?: string };
export type ReportOutput = {
  report_type?: string;
  title: string;
  period?: string;
  sections: { heading: string; content_md: string }[];
  highlights: string[];
  risks: string[];
  next_steps: string[];
};
export type InsightsOutput = {
  summary: string;
  key_points: string[];
  entities: string[];
  questions_to_ask: string[];
};

export const AGENT_LABEL: Record<string, string> = {
  research: "Research",
  email: "Email",
  meeting: "Meeting",
  report: "Report",
  document: "Document",
  chat: "Chat",
};

export const agentLabel = (name: string) => AGENT_LABEL[name] ?? name;

/** Agents the user can force from the composer ("Auto" = let the router decide). */
export const FORCEABLE_AGENTS: AgentName[] = ["research", "email", "report", "meeting", "document"];

/** Keep only well-formed sources (the field is untyped JSON in MessageOut). */
export function asSources(value: unknown): Source[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (s): s is Source =>
      typeof s === "object" &&
      s !== null &&
      typeof (s as Source).n === "number" &&
      typeof (s as Source).doc_id === "string" &&
      typeof (s as Source).filename === "string",
  );
}

export function asResults(value: unknown): ResultData[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (r): r is ResultData =>
      typeof r === "object" &&
      r !== null &&
      typeof (r as ResultData).agent === "string" &&
      typeof (r as ResultData).output === "object" &&
      (r as ResultData).output !== null,
  );
}
