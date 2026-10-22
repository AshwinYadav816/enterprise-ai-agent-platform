"use client";

import { CloudUpload } from "lucide-react";
import { useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ACCEPT_ATTRIBUTE, MAX_UPLOAD_MB, validateFile } from "@/lib/documents";
import { cn } from "@/lib/utils";

export type RejectedFile = { file: File; reason: string };

type DropzoneProps = {
  /** Called with the files that passed the client-side checks and those that didn't. */
  onFiles: (accepted: File[], rejected: RejectedFile[]) => void;
  disabled?: boolean;
};

export function splitFiles(files: Iterable<File>): { accepted: File[]; rejected: RejectedFile[] } {
  const accepted: File[] = [];
  const rejected: RejectedFile[] = [];
  for (const file of files) {
    const reason = validateFile(file);
    if (reason) rejected.push({ file, reason });
    else accepted.push(file);
  }
  return { accepted, rejected };
}

/** Drag-and-drop area with a "Browse files" button (keyboard and screen-reader friendly). */
export function Dropzone({ onFiles, disabled }: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const [dragging, setDragging] = useState(false);

  const take = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const { accepted, rejected } = splitFiles(Array.from(files));
    onFiles(accepted, rejected);
  };

  return (
    <div
      data-testid="dropzone"
      onDragOver={(e) => {
        if (disabled) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) take(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-input bg-card px-6 py-10 text-center transition-colors duration-150",
        dragging && "border-primary bg-blue-tint",
        disabled && "opacity-60",
      )}
    >
      <CloudUpload className="size-8 text-muted-foreground" aria-hidden />
      <div className="space-y-1">
        <p className="font-medium">Drop files here</p>
        <p id={hintId} className="type-small text-muted-foreground">
          PDF, Word, PowerPoint or Excel · up to {MAX_UPLOAD_MB} MB each
        </p>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        aria-describedby={hintId}
        onClick={() => inputRef.current?.click()}
      >
        Browse files
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT_ATTRIBUTE}
        className="sr-only"
        tabIndex={-1}
        aria-label="Choose files to upload"
        data-testid="file-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = ""; // allow picking the same file again
        }}
      />
    </div>
  );
}
