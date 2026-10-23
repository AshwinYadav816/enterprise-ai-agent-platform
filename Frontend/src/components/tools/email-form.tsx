"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useId } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";

import { SubmitLabel } from "@/components/tools/tool-layout";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useRestoredDraft, useSaveDraft } from "@/lib/hooks/use-stored-state";
import type { EmailRequest, EmailTask, EmailTone } from "@/lib/hooks/use-tools";
import { asOneOf, asRecord, asString } from "@/lib/storage";

export const EMAIL_TASKS: {
  value: EmailTask;
  label: string;
  textLabel: string;
  placeholder: string;
}[] = [
  {
    value: "draft",
    label: "Draft",
    textLabel: "What should the email say?",
    placeholder: "Who it's for, the key points, any dates or asks…",
  },
  { value: "rewrite", label: "Rewrite", textLabel: "Your draft", placeholder: "Paste your draft…" },
  {
    value: "grammar",
    label: "Fix grammar",
    textLabel: "Text to correct",
    placeholder: "Paste the text to correct…",
  },
  { value: "tone", label: "Change tone", textLabel: "Your email", placeholder: "Paste the email…" },
  {
    value: "summarize_thread",
    label: "Summarize thread",
    textLabel: "The email thread",
    placeholder: "Paste the whole thread, oldest or newest first…",
  },
];

/** Tasks where the tone matters (the others keep the writer's voice). */
export const TONE_TASKS = new Set<EmailTask>(["draft", "rewrite", "tone"]);

export const TONES: { value: EmailTone; label: string }[] = [
  { value: "formal", label: "Formal" },
  { value: "friendly", label: "Friendly" },
  { value: "concise", label: "Concise" },
  { value: "persuasive", label: "Persuasive" },
];

const schema = z.object({
  task: z.enum(["draft", "rewrite", "grammar", "tone", "summarize_thread"]),
  tone: z.enum(["formal", "friendly", "concise", "persuasive"]),
  text: z
    .string()
    .trim()
    .min(1, "Add some text to work with")
    .max(20_000, "Keep it under 20,000 characters"),
});
type Values = z.infer<typeof schema>;

const EMPTY: Values = { task: "draft", tone: "friendly", text: "" };
const parseDraft = asRecord<Values>({
  task: asOneOf(EMAIL_TASKS.map((t) => t.value)),
  tone: asOneOf(TONES.map((t) => t.value)),
  text: asString,
});

export function EmailForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: EmailRequest) => void;
  pending: boolean;
}) {
  const textId = useId();
  const toneId = useId();
  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: useRestoredDraft("tool:email", EMPTY, parseDraft), // survives a refresh
  });
  const values = useWatch({ control }) as Values;
  useSaveDraft("tool:email", values, EMPTY);
  const task = values.task;
  const current = EMAIL_TASKS.find((t) => t.value === task) ?? EMAIL_TASKS[0];
  const showTone = TONE_TASKS.has(task);

  return (
    <form
      noValidate
      className="space-y-5"
      onSubmit={handleSubmit(({ task, tone, text }) =>
        onSubmit({ task, text, ...(TONE_TASKS.has(task) ? { tone } : {}) }),
      )}
    >
      <Controller
        control={control}
        name="task"
        render={({ field }) => (
          <Tabs value={field.value} onValueChange={(v) => field.onChange(v as EmailTask)}>
            <TabsList
              aria-label="What to do"
              className="grid w-full grid-cols-2 gap-0.5 group-data-horizontal/tabs:h-auto"
            >
              {EMAIL_TASKS.map((t) => (
                <TabsTrigger key={t.value} value={t.value} className="h-8">
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
      />

      {showTone && (
        <Field>
          <FieldLabel htmlFor={toneId}>Tone</FieldLabel>
          <Controller
            control={control}
            name="tone"
            render={({ field }) => (
              <Select value={field.value} onValueChange={(v) => field.onChange(v as EmailTone)}>
                <SelectTrigger id={toneId} className="w-full sm:w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TONES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      )}

      <Field data-invalid={!!errors.text || undefined}>
        <FieldLabel htmlFor={textId}>{current.textLabel}</FieldLabel>
        <Textarea
          id={textId}
          rows={9}
          placeholder={current.placeholder}
          aria-invalid={!!errors.text || undefined}
          className="max-h-[50svh] min-h-40"
          {...register("text")}
        />
        {errors.text ? (
          <FieldError>{errors.text.message}</FieldError>
        ) : (
          <FieldDescription>Nothing is sent anywhere: you get a draft to copy.</FieldDescription>
        )}
      </Field>

      <Button type="submit" className="w-full" disabled={pending}>
        <SubmitLabel pending={pending} idle="Write email" busy="Writing…" />
      </Button>
    </form>
  );
}
