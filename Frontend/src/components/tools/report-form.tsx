"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { FileText, X } from "lucide-react";
import { useId, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { TextField } from "@/components/auth/form-fields";
import { DocPicker, type PickedDoc } from "@/components/chat/doc-picker";
import { SubmitLabel } from "@/components/tools/tool-layout";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import type { ReportRequest, ReportType } from "@/lib/hooks/use-tools";

const REPORT_TYPES: { value: ReportType; label: string; period: string }[] = [
  { value: "weekly", label: "Weekly", period: "e.g. 14–20 Oct 2026" },
  { value: "monthly", label: "Monthly", period: "e.g. October 2026" },
  { value: "sprint", label: "Sprint", period: "e.g. Sprint 7 (6–17 Oct)" },
  { value: "project", label: "Project", period: "e.g. Atlas launch, Q3 2026" },
];

const schema = z.object({
  report_type: z.enum(["weekly", "monthly", "sprint", "project"]),
  period: z.string().trim().min(1, "Say which period it covers").max(100),
  instruction: z
    .string()
    .trim()
    .min(1, "Tell the report writer what to cover")
    .max(4000, "Keep it under 4,000 characters"),
});
type Values = z.infer<typeof schema>;

export function ReportForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: ReportRequest) => void;
  pending: boolean;
}) {
  const instructionId = useId();
  const [docs, setDocs] = useState<PickedDoc[]>([]);
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { report_type: "weekly", period: "", instruction: "" },
  });
  const reportType = useWatch({ control, name: "report_type" });
  const type = REPORT_TYPES.find((t) => t.value === reportType) ?? REPORT_TYPES[0];

  return (
    <form
      noValidate
      className="space-y-5"
      onSubmit={handleSubmit((values) =>
        onSubmit({ ...values, doc_ids: docs.length ? docs.map((d) => d.id) : undefined }),
      )}
    >
      <Controller
        control={control}
        name="report_type"
        render={({ field }) => (
          <Tabs value={field.value} onValueChange={(v) => field.onChange(v as ReportType)}>
            <TabsList aria-label="Report type" className="w-full">
              {REPORT_TYPES.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
      />

      <TextField
        label="Period"
        placeholder={type.period}
        maxLength={100}
        error={errors.period?.message}
        {...register("period")}
      />

      <Field data-invalid={!!errors.instruction || undefined}>
        <FieldLabel htmlFor={instructionId}>What should it cover?</FieldLabel>
        <Textarea
          id={instructionId}
          rows={6}
          placeholder="Progress on the onboarding project, blockers, and what's next. Audience: leadership."
          aria-invalid={!!errors.instruction || undefined}
          className="max-h-[40svh] min-h-32"
          {...register("instruction")}
        />
        {errors.instruction && <FieldError>{errors.instruction.message}</FieldError>}
      </Field>

      <Field>
        <div className="flex items-center justify-between gap-2">
          <FieldLabel>Source documents (optional)</FieldLabel>
          <DocPicker value={docs} onChange={setDocs} disabled={pending} />
        </div>
        {docs.length > 0 ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Selected documents">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="inline-flex items-center gap-1.5 rounded-full border bg-background py-0.5 pr-1 pl-2.5 text-xs"
              >
                <FileText className="size-3.5" aria-hidden />
                <span className="max-w-48 truncate">{doc.filename}</span>
                <button
                  type="button"
                  onClick={() => setDocs(docs.filter((d) => d.id !== doc.id))}
                  aria-label={`Remove ${doc.filename}`}
                  className="rounded-full p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  <X className="size-3" />
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <FieldDescription>
            Without documents the report uses your instructions only.
          </FieldDescription>
        )}
      </Field>

      <Button type="submit" className="w-full" disabled={pending}>
        <SubmitLabel pending={pending} idle="Write report" busy="Writing…" />
      </Button>
    </form>
  );
}
