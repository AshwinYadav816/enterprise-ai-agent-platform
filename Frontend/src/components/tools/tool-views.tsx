"use client";

import { Mail, NotebookPen, Users } from "lucide-react";

import { EmailForm } from "@/components/tools/email-form";
import { MeetingForm } from "@/components/tools/meeting-form";
import { ReportForm } from "@/components/tools/report-form";
import { ToolLayout } from "@/components/tools/tool-layout";
import { useEmail, useMeetingSummary, useReport } from "@/lib/hooks/use-tools";

export function MeetingsView() {
  const run = useMeetingSummary();
  return (
    <ToolLayout
      eyebrow="Meeting assistant"
      title="Meetings"
      description="Turn a transcript into a summary, decisions and action items with owners."
      form={<MeetingForm onSubmit={(input) => run.mutate(input)} pending={run.isPending} />}
      run={run}
      empty={{
        icon: Users,
        title: "Your summary will appear here",
        description: "Paste a transcript or upload a .txt, .vtt or .docx file.",
      }}
    />
  );
}

export function ReportsView() {
  const run = useReport();
  return (
    <ToolLayout
      eyebrow="Report generator"
      title="Reports"
      description="Weekly, monthly, sprint and project reports, optionally grounded in your documents."
      form={<ReportForm onSubmit={(body) => run.mutate(body)} pending={run.isPending} />}
      run={run}
      empty={{
        icon: NotebookPen,
        title: "Your report will appear here",
        description: "Pick a type and period, and say what it should cover.",
      }}
    />
  );
}

export function EmailView() {
  const run = useEmail();
  return (
    <ToolLayout
      eyebrow="Email assistant"
      title="Email"
      description="Draft, rewrite, fix or summarize emails in the right tone."
      form={<EmailForm onSubmit={(body) => run.mutate(body)} pending={run.isPending} />}
      run={run}
      empty={{
        icon: Mail,
        title: "Your email will appear here",
        description: "Choose what to do, add your text, and you'll get a subject and body to copy.",
      }}
    />
  );
}
