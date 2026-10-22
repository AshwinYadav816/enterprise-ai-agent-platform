import { cn } from "@/lib/utils";

export const PRODUCT_NAME = "Agent Platform";

/** Product name in Newsreader, editorial blue, with the coral signature dot. */
export function Wordmark({
  className,
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-baseline font-serif font-semibold tracking-tight text-primary",
        compact ? "text-lg" : "text-2xl",
        className,
      )}
    >
      {compact ? "AP" : PRODUCT_NAME}
      <span aria-hidden className="ml-0.5 inline-block size-1.5 rounded-full bg-coral" />
    </span>
  );
}
