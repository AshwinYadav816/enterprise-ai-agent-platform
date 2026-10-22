"use client";

import { ExternalLink, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { downloadFile } from "@/lib/api/download";
import { toastError } from "@/lib/api/errors";
import { cleanSnippet } from "@/lib/chat/citations";
import type { Source } from "@/lib/chat/types";

export function openSource(source: Pick<Source, "doc_id" | "filename">) {
  downloadFile(`/documents/${source.doc_id}/download`, source.filename).catch(toastError);
}

/** `[n]` in an answer: a superscript chip; click/Enter opens the source's details. */
export function Citation({ n, source }: { n: number; source: Source }) {
  const where = source.page ? `, page ${source.page}` : "";
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Source ${n}: ${source.filename}${where}`}
          className="relative -top-1.5 mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-tint px-1 align-baseline font-sans text-[0.6875rem] leading-none font-semibold text-primary transition-colors duration-150 hover:bg-primary hover:text-primary-foreground"
        >
          {n}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 gap-2 p-4" align="start">
        <div className="flex items-start gap-2 text-sm font-medium">
          <FileText className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <span className="min-w-0 break-words">
            {source.filename}
            {source.page ? (
              <span className="font-normal text-muted-foreground"> · page {source.page}</span>
            ) : null}
          </span>
        </div>
        {source.snippet && (
          <p className="line-clamp-6 type-small text-muted-foreground">
            “{cleanSnippet(source.snippet)}”
          </p>
        )}
        <Button
          variant="link"
          size="sm"
          className="h-auto justify-start px-0"
          onClick={() => openSource(source)}
        >
          Open document <ExternalLink />
        </Button>
      </PopoverContent>
    </Popover>
  );
}
