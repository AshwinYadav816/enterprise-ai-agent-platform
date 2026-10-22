"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

import { Markdown } from "@/components/chat/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { downloadFile } from "@/lib/api/download";
import { toastError } from "@/lib/api/errors";
import type {
  EmailOutput,
  InsightsOutput,
  MeetingOutput,
  ReportOutput,
  ResultData,
} from "@/lib/chat/types";
import { cn } from "@/lib/utils";

/** Agents whose result is a card (research/chat results are the answer text itself). */
const CARD_AGENTS = new Set(["meeting", "email", "report", "document"]);
export const hasCard = (result: ResultData) => CARD_AGENTS.has(result.agent);

const EYEBROW: Record<string, string> = {
  meeting: "Meeting summary",
  email: "Email draft",
  report: "Report",
  document: "Document insights",
};

type ResultCardProps = {
  result: ResultData;
  /** For "Download PDF": the saved message and this result's position in it. */
  pdf?: { conversationId: string; messageId: string; index: number };
};

export function ResultCard({ result, pdf }: ResultCardProps) {
  if (!hasCard(result)) return null;
  const { title, body, copyText } = renderResult(result);

  return (
    <section className="my-4 overflow-hidden rounded-lg border bg-card font-sans">
      <div className="space-y-1 px-5 pt-4">
        <p className="type-eyebrow text-muted-foreground">{EYEBROW[result.agent]}</p>
        <h3 className="type-title text-balance">{title}</h3>
      </div>
      <div className="space-y-4 px-5 py-4 text-[0.9375rem] leading-relaxed">{body}</div>
      <div className="flex flex-wrap gap-1 border-t bg-muted/50 px-3 py-2">
        <CopyButton text={copyText} label="Copy" />
        {pdf && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() =>
              downloadFile(
                `/conversations/${pdf.conversationId}/messages/${pdf.messageId}/results/${pdf.index}/pdf`,
                `${result.agent}.pdf`,
              ).catch(toastError)
            }
          >
            <Download /> Download PDF
          </Button>
        )}
      </div>
    </section>
  );
}

export function CopyButton({
  text,
  label,
  className,
}: {
  text: string;
  label: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="ghost"
      size="sm"
      className={className}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch (error) {
          toastError(error);
        }
      }}
    >
      {copied ? <Check /> : <Copy />} {copied ? "Copied" : label}
    </Button>
  );
}

// ---- per-agent rendering

const list = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((v): v is string => typeof v === "string" && v.trim() !== "")
    : [];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h4 className="type-eyebrow text-muted-foreground">{title}</h4>
      {children}
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}

function renderResult(result: ResultData): {
  title: string;
  body: React.ReactNode;
  copyText: string;
} {
  const markdown = typeof result.markdown === "string" ? result.markdown : undefined;

  if (result.agent === "meeting") {
    const out = result.output as Partial<MeetingOutput>;
    const decisions = list(out.key_decisions);
    const questions = list(out.open_questions);
    const actions = Array.isArray(out.action_items) ? out.action_items : [];
    return {
      title: `${decisions.length} ${decisions.length === 1 ? "decision" : "decisions"} · ${actions.length} action ${actions.length === 1 ? "item" : "items"}`,
      copyText: markdown ?? out.summary ?? "",
      body: (
        <>
          {out.summary && <p>{out.summary}</p>}
          {decisions.length > 0 && (
            <Section title="Key decisions">
              <Bullets items={decisions} />
            </Section>
          )}
          {actions.length > 0 && (
            <Section title="Action items">
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60 text-left">
                    <tr>
                      <th className="px-3 py-2 font-semibold">Task</th>
                      <th className="px-3 py-2 font-semibold">Owner</th>
                      <th className="px-3 py-2 font-semibold">Due</th>
                    </tr>
                  </thead>
                  <tbody>
                    {actions.map((a, i) => {
                      const unassigned = !a.owner || a.owner.toLowerCase() === "unassigned";
                      return (
                        <tr key={i} className="border-t align-top">
                          <td className="px-3 py-2">{a.task}</td>
                          <td
                            className={cn(
                              "px-3 py-2",
                              unassigned && "text-muted-foreground italic",
                            )}
                          >
                            {unassigned ? "Unassigned" : a.owner}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                            {a.due_date || "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Section>
          )}
          {questions.length > 0 && (
            <Section title="Open questions">
              <Bullets items={questions} />
            </Section>
          )}
        </>
      ),
    };
  }

  if (result.agent === "email") {
    const out = result.output as Partial<EmailOutput>;
    const subject = out.subject ?? "";
    const body = out.body ?? "";
    return {
      title: subject || "Email",
      copyText: `Subject: ${subject}\n\n${body}`,
      body: (
        <>
          <div className="flex items-start justify-between gap-2 rounded-md border bg-background px-3 py-2">
            <p className="min-w-0">
              <span className="mr-2 type-eyebrow text-muted-foreground">Subject</span>
              {subject}
            </p>
            <CopyButton text={subject} label="Copy subject" className="-my-1 shrink-0" />
          </div>
          <div className="relative rounded-md border bg-background px-4 py-3">
            <p className="whitespace-pre-wrap">{body}</p>
            <CopyButton text={body} label="Copy body" className="mt-2 -ml-2" />
          </div>
          {out.notes && <p className="type-small text-muted-foreground">{out.notes}</p>}
        </>
      ),
    };
  }

  if (result.agent === "report") {
    const out = result.output as Partial<ReportOutput>;
    const sections = Array.isArray(out.sections) ? out.sections : [];
    return {
      title: out.title || "Report",
      copyText: markdown ?? "",
      body: (
        <>
          {out.period && out.period !== "Not specified" && (
            <Badge variant="outline">{out.period}</Badge>
          )}
          {sections.map((section, i) => (
            <Section key={i} title={section.heading}>
              <Markdown>{section.content_md}</Markdown>
            </Section>
          ))}
          {list(out.highlights).length > 0 && (
            <Section title="Highlights">
              <Bullets items={list(out.highlights)} />
            </Section>
          )}
          {list(out.risks).length > 0 && (
            <Section title="Risks">
              <Bullets items={list(out.risks)} />
            </Section>
          )}
          {list(out.next_steps).length > 0 && (
            <Section title="Next steps">
              <Bullets items={list(out.next_steps)} />
            </Section>
          )}
        </>
      ),
    };
  }

  // document insights
  const out = result.output as Partial<InsightsOutput>;
  const keyPoints = list(out.key_points);
  const entities = list(out.entities);
  const questions = list(out.questions_to_ask);
  return {
    title: "What this document says",
    copyText: [out.summary ?? "", ...keyPoints.map((p) => `- ${p}`)].join("\n"),
    body: (
      <>
        {out.summary && <p>{out.summary}</p>}
        {keyPoints.length > 0 && (
          <Section title="Key points">
            <Bullets items={keyPoints} />
          </Section>
        )}
        {entities.length > 0 && (
          <Section title="People, teams and terms">
            <div className="flex flex-wrap gap-1.5">
              {entities.map((e) => (
                <Badge key={e} variant="secondary">
                  {e}
                </Badge>
              ))}
            </div>
          </Section>
        )}
        {questions.length > 0 && (
          <Section title="Questions to ask">
            <Bullets items={questions} />
          </Section>
        )}
      </>
    ),
  };
}
