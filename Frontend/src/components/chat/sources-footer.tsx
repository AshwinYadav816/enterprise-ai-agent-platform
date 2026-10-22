"use client";

import { openSource } from "@/components/chat/citation";
import { uniqueSources } from "@/lib/chat/citations";
import type { Source } from "@/lib/chat/types";

/** The sources used for an answer, as footnotes under a thin rule. */
export function SourcesFooter({ sources }: { sources: Source[] }) {
  const items = uniqueSources(sources);
  if (items.length === 0) return null;
  return (
    <div className="mt-4 space-y-1.5 border-t pt-3 font-sans">
      <p className="type-eyebrow text-muted-foreground">Sources</p>
      <ol className="space-y-1">
        {items.map((s) => (
          <li key={`${s.n}-${s.doc_id}-${s.page ?? ""}`} className="flex gap-2 type-small">
            <span className="w-5 shrink-0 font-semibold text-primary">[{s.n}]</span>
            <button
              type="button"
              onClick={() => openSource(s)}
              className="min-w-0 truncate text-left text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              title={s.snippet}
            >
              {s.filename}
              {s.page ? `, page ${s.page}` : ""}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
