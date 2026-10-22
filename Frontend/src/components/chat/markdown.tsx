"use client";

import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Citation } from "@/components/chat/citation";
import { CITE_PREFIX, linkCitations, sourceFor } from "@/lib/chat/citations";
import type { Source } from "@/lib/chat/types";
import { cn } from "@/lib/utils";

type MarkdownProps = {
  children: string;
  /** Enables `[n]` citation chips for the sources that exist. */
  sources?: Source[];
  /** The coral blinking cursor at the end of the text, while the answer streams. */
  cursor?: boolean;
  className?: string;
};

/**
 * AI text as Markdown (GFM tables, lists, code). Raw HTML is never rendered: react-markdown
 * escapes it, and links are limited to http(s)/mailto by its default URL transform.
 */
export const Markdown = memo(function Markdown({
  children,
  sources = [],
  cursor = false,
  className,
}: MarkdownProps) {
  const components: Components = {
    a({ href, children: text }) {
      if (href?.startsWith(CITE_PREFIX)) {
        const n = Number(href.slice(CITE_PREFIX.length));
        const source = sourceFor(sources, n);
        if (source) return <Citation n={n} source={source} />;
        return <>[{text}]</>;
      }
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-primary underline underline-offset-4"
        >
          {text}
        </a>
      );
    },
    p: ({ children: c }) => <p className="my-3 first:mt-0 last:mb-0">{c}</p>,
    ul: ({ children: c }) => <ul className="my-3 list-disc space-y-1 pl-6">{c}</ul>,
    ol: ({ children: c }) => <ol className="my-3 list-decimal space-y-1 pl-6">{c}</ol>,
    h1: ({ children: c }) => <h3 className="mt-5 mb-2 type-title">{c}</h3>,
    h2: ({ children: c }) => <h3 className="mt-5 mb-2 type-title">{c}</h3>,
    h3: ({ children: c }) => <h4 className="mt-4 mb-1.5 text-lg font-semibold">{c}</h4>,
    h4: ({ children: c }) => <h4 className="mt-4 mb-1.5 font-semibold">{c}</h4>,
    blockquote: ({ children: c }) => (
      <blockquote className="my-3 border-l-2 border-border pl-4 text-muted-foreground">
        {c}
      </blockquote>
    ),
    hr: () => <hr className="my-5 border-border" />,
    table: ({ children: c }) => (
      <div className="my-4 overflow-x-auto rounded-lg border bg-card font-sans text-sm">
        <table className="w-full border-collapse">{c}</table>
      </div>
    ),
    thead: ({ children: c }) => <thead className="bg-muted/60">{c}</thead>,
    th: ({ children: c }) => <th className="border-b px-3 py-2 text-left font-semibold">{c}</th>,
    td: ({ children: c }) => <td className="border-b px-3 py-2 align-top">{c}</td>,
    pre: ({ children: c }) => (
      <pre className="my-3 overflow-x-auto rounded-lg border bg-muted/60 p-3 font-mono text-[0.8125rem] leading-relaxed">
        {c}
      </pre>
    ),
    code: ({ className: lang, children: c }) => (
      <code
        className={cn(
          "font-mono text-[0.85em]",
          !lang && "rounded bg-muted px-1 py-0.5 [pre_&]:bg-transparent [pre_&]:p-0",
        )}
      >
        {c}
      </code>
    ),
  };

  return (
    <div
      className={cn(
        "break-words",
        // keep the cursor on the last line of text instead of below it
        cursor && "[&>p:has(+[data-cursor])]:inline",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {linkCitations(children, sources)}
      </ReactMarkdown>
      {cursor && (
        <span
          data-cursor
          aria-hidden
          className="ml-0.5 inline-block h-[1.1em] w-0.5 translate-y-[0.2em] animate-pulse bg-coral"
        />
      )}
    </div>
  );
});
