"use client";

import { FileText, Upload, X } from "lucide-react";
import { useId, useRef, useState } from "react";

import { TextField } from "@/components/auth/form-fields";
import { wordCount } from "@/components/chat/transcript-attach";
import { SubmitLabel } from "@/components/tools/tool-layout";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { extensionOf } from "@/lib/documents";
import { formatBytes } from "@/lib/format";
import type { MeetingInput } from "@/lib/hooks/use-tools";

const MAX_CHARS = 200_000;
const MAX_FILE_BYTES = 5 * 1024 * 1024; // backend MAX_TRANSCRIPT_FILE_BYTES
const FILE_TYPES = ["txt", "vtt", "docx"];

export function MeetingForm({
  onSubmit,
  pending,
}: {
  onSubmit: (input: MeetingInput) => void;
  pending: boolean;
}) {
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [title, setTitle] = useState("");
  const [transcript, setTranscript] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const transcriptId = useId();

  const pickFile = (picked: File | undefined) => {
    if (!picked) return;
    if (!FILE_TYPES.includes(extensionOf(picked.name))) {
      setError("Use a .txt, .vtt or .docx transcript.");
      return;
    }
    if (picked.size > MAX_FILE_BYTES) {
      setError("That file is larger than 5 MB.");
      return;
    }
    setError(null);
    setFile(picked);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "paste") {
      if (!transcript.trim()) return setError("Paste the meeting transcript.");
      if (transcript.length > MAX_CHARS)
        return setError("That transcript is over 200,000 characters.");
      setError(null);
      onSubmit({ transcript: transcript.trim(), title });
    } else {
      if (!file) return setError("Choose a transcript file.");
      setError(null);
      onSubmit({ file, title });
    }
  };

  return (
    <form noValidate className="space-y-5" onSubmit={submit}>
      <Tabs
        value={mode}
        onValueChange={(v) => {
          setMode(v as "paste" | "upload");
          setError(null);
        }}
      >
        <TabsList aria-label="Transcript source" className="w-full">
          <TabsTrigger value="paste">Paste</TabsTrigger>
          <TabsTrigger value="upload">Upload</TabsTrigger>
        </TabsList>

        <TabsContent value="paste" className="mt-4">
          <Field data-invalid={!!error || undefined}>
            <FieldLabel htmlFor={transcriptId}>Transcript</FieldLabel>
            <Textarea
              id={transcriptId}
              rows={10}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              maxLength={MAX_CHARS}
              placeholder={"Rohit: I'll update the notes by Friday.\nAna: Let's ship on Friday."}
              className="max-h-[50svh] min-h-48 font-mono text-[0.8125rem]"
            />
            <FieldDescription>{wordCount(transcript).toLocaleString()} words</FieldDescription>
          </Field>
        </TabsContent>

        <TabsContent value="upload" className="mt-4">
          <div className="flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-input px-4 py-8 text-center">
            {file ? (
              <div className="flex w-full items-center gap-3 rounded-md border bg-background px-3 py-2 text-left">
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{file.name}</p>
                  <p className="type-small text-muted-foreground">{formatBytes(file.size)}</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => setFile(null)}
                  aria-label={`Remove ${file.name}`}
                >
                  <X />
                </Button>
              </div>
            ) : (
              <>
                <Upload className="size-6 text-muted-foreground" aria-hidden />
                <p className="type-small text-muted-foreground">.txt, .vtt or .docx · up to 5 MB</p>
              </>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileRef.current?.click()}
            >
              {file ? "Choose another file" : "Choose a file"}
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.vtt,.docx"
              className="sr-only"
              tabIndex={-1}
              aria-label="Transcript file"
              data-testid="transcript-file"
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>
        </TabsContent>
      </Tabs>

      {error && <FieldError>{error}</FieldError>}

      <TextField
        label="Title (optional)"
        placeholder="e.g. Q3 planning sync"
        maxLength={200}
        value={title}
        onChange={(e) => setTitle(e.target.value)}
      />

      <Button type="submit" className="w-full" disabled={pending}>
        <SubmitLabel pending={pending} idle="Summarize meeting" busy="Summarizing…" />
      </Button>
    </form>
  );
}
