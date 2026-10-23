"use client";

import { CircleCheck, CircleX, FileText, Loader2, X } from "lucide-react";
import { useId, useState } from "react";
import { toast } from "sonner";

import { Dropzone, type RejectedFile } from "@/components/documents/dropzone";
import { VisibilitySelect } from "@/components/documents/visibility-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { errorMessage } from "@/lib/api/errors";
import { visibilityOptions, type UserRole } from "@/lib/documents";
import { formatBytes } from "@/lib/format";
import { useUploadDocument } from "@/lib/hooks/use-documents";
import { useStoredState } from "@/lib/hooks/use-stored-state";
import { asOneOf } from "@/lib/storage";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

type ItemState = "pending" | "uploading" | "done" | "error" | "rejected";
type Item = { key: string; file: File; state: ItemState; message?: string };

let nextKey = 0;
const newKey = () => `upload-${++nextKey}`;

export function UploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { user } = useAuth();
  const upload = useUploadDocument();
  const visibilityId = useId();
  const [items, setItems] = useState<Item[]>([]);
  // Remembered for the next upload; only a level this user may still pick.
  const [visibility, setVisibility] = useStoredState<UserRole>(
    "pref",
    "upload-visibility",
    "employee",
    asOneOf(user ? visibilityOptions(user.role) : []),
  );
  const [running, setRunning] = useState(false);

  const pending = items.filter((i) => i.state === "pending");
  const finished =
    items.length > 0 && items.every((i) => !["pending", "uploading"].includes(i.state));

  const update = (key: string, patch: Partial<Item>) =>
    setItems((list) => list.map((i) => (i.key === key ? { ...i, ...patch } : i)));

  const addFiles = (accepted: File[], rejected: RejectedFile[]) =>
    setItems((list) => [
      ...list,
      ...accepted.map((file) => ({ key: newKey(), file, state: "pending" as const })),
      ...rejected.map(({ file, reason }) => ({
        key: newKey(),
        file,
        state: "rejected" as const,
        message: reason,
      })),
    ]);

  // One file at a time: predictable for the server and easy to follow in the list.
  const startUpload = async () => {
    setRunning(true);
    let succeeded = 0;
    for (const item of pending) {
      update(item.key, { state: "uploading" });
      try {
        await upload.mutateAsync({ file: item.file, visibility });
        update(item.key, { state: "done" });
        succeeded += 1;
      } catch (error) {
        update(item.key, { state: "error", message: errorMessage(error) });
      }
    }
    setRunning(false);
    if (succeeded > 0) {
      toast.success(succeeded === 1 ? "Uploaded 1 document" : `Uploaded ${succeeded} documents`, {
        description: "Processing has started; they'll be ready shortly.",
      });
    }
  };

  const close = (next: boolean) => {
    if (running) return; // keep the dialog while files are uploading
    onOpenChange(next);
    if (!next) setItems([]);
  };

  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg" showCloseButton={!running}>
        <DialogHeader>
          <DialogTitle>Upload documents</DialogTitle>
          <DialogDescription>
            They&apos;re added to your knowledge base so the assistant can answer from them.
          </DialogDescription>
        </DialogHeader>

        <Dropzone onFiles={addFiles} disabled={running} />

        {items.length > 0 && (
          <ul className="max-h-56 space-y-1.5 overflow-y-auto" aria-label="Files to upload">
            {items.map((item) => (
              <FileRow
                key={item.key}
                item={item}
                onRemove={
                  running || item.state === "uploading" || item.state === "done"
                    ? undefined
                    : () => setItems((list) => list.filter((i) => i.key !== item.key))
                }
              />
            ))}
          </ul>
        )}

        <div className="space-y-2">
          <Label htmlFor={visibilityId}>Who can see these documents</Label>
          <VisibilitySelect
            id={visibilityId}
            role={user.role}
            value={visibility}
            onChange={setVisibility}
            disabled={running}
          />
        </div>

        <DialogFooter>
          {finished ? (
            <Button onClick={() => close(false)}>Done</Button>
          ) : (
            <>
              <Button variant="outline" onClick={() => close(false)} disabled={running}>
                Cancel
              </Button>
              <Button onClick={startUpload} disabled={running || pending.length === 0}>
                {running && <Loader2 className="animate-spin" aria-hidden />}
                {running
                  ? "Uploading…"
                  : pending.length > 1
                    ? `Upload ${pending.length} files`
                    : "Upload"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const STATE_TEXT: Record<ItemState, string> = {
  pending: "Ready to upload",
  uploading: "Uploading…",
  done: "Uploaded",
  error: "Failed",
  rejected: "Can't upload",
};

function FileRow({ item, onRemove }: { item: Item; onRemove?: () => void }) {
  const bad = item.state === "error" || item.state === "rejected";
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-md border bg-card px-3 py-2",
        bad && "border-destructive/30 bg-destructive-tint/40",
      )}
    >
      <span className="mt-0.5 shrink-0" aria-hidden>
        {item.state === "uploading" ? (
          <Loader2 className="size-4 animate-spin text-primary" />
        ) : item.state === "done" ? (
          <CircleCheck className="size-4 text-success" />
        ) : bad ? (
          <CircleX className="size-4 text-destructive" />
        ) : (
          <FileText className="size-4 text-muted-foreground" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.file.name}</p>
        <p className={cn("type-small", bad ? "text-destructive" : "text-muted-foreground")}>
          {formatBytes(item.file.size)} · {item.message ?? STATE_TEXT[item.state]}
        </p>
      </div>
      {onRemove && (
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={onRemove}
          aria-label={`Remove ${item.file.name}`}
        >
          <X />
        </Button>
      )}
    </li>
  );
}
