"use client";

import { FileUp, Mic } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export const MAX_TRANSCRIPT_CHARS = 200_000; // backend SendMessageRequest.transcript

export const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

/**
 * Attach a meeting transcript to the next message ("summarize this meeting and email the action
 * items to the team"). Paste it, or load a text file (.txt, .vtt, .srt, .md).
 */
export function TranscriptAttach({
  value,
  onChange,
  disabled,
}: {
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const fieldId = useId();

  const loadFile = async (file: File | undefined) => {
    if (!file) return;
    const text = await file.text();
    if (text.length > MAX_TRANSCRIPT_CHARS) {
      setError("That transcript is too long (over 200,000 characters).");
      return;
    }
    setError(null);
    setDraft(text);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) {
          setDraft(value ?? "");
          setError(null);
        }
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled}
          aria-label="Attach a meeting transcript"
        >
          <Mic />
          <span className="hidden sm:inline">Transcript</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Attach a meeting transcript</DialogTitle>
          <DialogDescription>
            Then ask, for example: &ldquo;Summarize this meeting and email the action items to the
            team.&rdquo;
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor={fieldId}>Transcript</Label>
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}>
              <FileUp /> Load a file
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".txt,.vtt,.srt,.md,text/plain"
              className="sr-only"
              tabIndex={-1}
              aria-label="Load a transcript file"
              onChange={(e) => {
                void loadFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>
          <Textarea
            id={fieldId}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={MAX_TRANSCRIPT_CHARS}
            placeholder="Paste the transcript here…"
            className="max-h-[50svh] min-h-48 font-mono text-[0.8125rem]"
          />
          <p className="type-small text-muted-foreground">
            {wordCount(draft).toLocaleString()} words · .txt, .vtt, .srt or .md files
          </p>
          {error && (
            <p className="type-small text-destructive" role="alert">
              {error}
            </p>
          )}
        </div>
        <DialogFooter>
          {value && (
            <Button
              variant="outline"
              onClick={() => {
                onChange(null);
                setOpen(false);
              }}
            >
              Remove
            </Button>
          )}
          <Button
            disabled={!draft.trim()}
            onClick={() => {
              onChange(draft.trim());
              setOpen(false);
            }}
          >
            Attach
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
