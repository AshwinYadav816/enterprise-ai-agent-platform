import type { Source } from "@/lib/chat/types";

export const CITE_PREFIX = "#cite-";

const CODE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;
const MARKER = /\[(\d{1,3})\](?![(:])/g; // [n] that isn't already a link or a reference definition

/**
 * Turn `[n]` into a markdown link `[n](#cite-n)` when source n exists, outside code. Unknown
 * numbers stay plain text, so the model can't produce a chip that points nowhere.
 */
export function linkCitations(markdown: string, sources: Source[]): string {
  if (sources.length === 0) return markdown;
  const known = new Set(sources.map((s) => s.n));
  return markdown
    .split(CODE)
    .map((part, i) =>
      i % 2 === 1
        ? part // code: untouched
        : part.replace(MARKER, (match, n: string) =>
            known.has(Number(n)) ? `[${n}](${CITE_PREFIX}${n})` : match,
          ),
    )
    .join("");
}

/** Snippet text without the "[file.pdf — p.1]" marker the AI module puts on each passage. */
export function cleanSnippet(snippet: string): string {
  return snippet.replace(/^\s*\[[^\]\n]*\]\s*/, "").trim();
}

/** The source behind citation n (numbers restart per agent; the first match wins). */
export function sourceFor(sources: Source[], n: number): Source | undefined {
  return sources.find((s) => s.n === n);
}

/** One entry per (n, document, page), in order: the footnote list under an answer. */
export function uniqueSources(sources: Source[]): Source[] {
  const seen = new Set<string>();
  return sources.filter((s) => {
    const key = `${s.n}|${s.doc_id}|${s.page ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
