"use client";

import { History } from "lucide-react";
import Link from "next/link";

import { ResultCard } from "@/components/chat/result-card";
import { Button } from "@/components/ui/button";
import { formatDateTime } from "@/lib/format";
import { generationPdfPath, generationResult, type Generation } from "@/lib/hooks/use-tools";

/** A saved generation: the result card with Copy, Download PDF and (optionally) Open in History. */
export function GenerationView({
  generation,
  showHistoryLink = false,
  showHeader = true,
}: {
  generation: Generation;
  showHistoryLink?: boolean;
  /** false on the History detail page, whose heading already names it. */
  showHeader?: boolean;
}) {
  return (
    <div>
      <ResultCard
        className="my-0"
        result={generationResult(generation)}
        title={generation.title}
        showHeader={showHeader}
        pdfPath={generationPdfPath(generation.id)}
        actions={
          showHistoryLink && (
            <Button asChild variant="ghost" size="sm">
              <Link href={`/history/${generation.id}`}>
                <History /> Open in History
              </Link>
            </Button>
          )
        }
      />
      <p className="mt-2 type-small text-muted-foreground">
        Saved {formatDateTime(generation.created_at)}
      </p>
    </div>
  );
}
