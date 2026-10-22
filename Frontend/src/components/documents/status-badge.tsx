import { CircleCheck, CircleX } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { STATUS_LABEL, type DocumentStatus } from "@/lib/documents";

/** Status as text + icon (never colour alone). Failed shows the reason on hover/focus. */
export function StatusBadge({ status, error }: { status: DocumentStatus; error?: string | null }) {
  if (status === "processing") {
    return (
      <Badge variant="warning">
        <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-warning" />
        {STATUS_LABEL.processing}
      </Badge>
    );
  }
  if (status === "ready") {
    return (
      <Badge variant="success">
        <CircleCheck aria-hidden /> {STATUS_LABEL.ready}
      </Badge>
    );
  }
  const badge = (
    <Badge variant="destructive">
      <CircleX aria-hidden /> {STATUS_LABEL.failed}
    </Badge>
  );
  if (!error) return badge;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type="button" className="rounded-full" aria-label={`Failed: ${error}`}>
          {badge}
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{error}</TooltipContent>
    </Tooltip>
  );
}
