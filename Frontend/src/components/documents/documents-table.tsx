"use client";

import {
  Download,
  Ellipsis,
  FileSpreadsheet,
  FileText,
  FileType,
  Info,
  Presentation,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { StatusBadge } from "@/components/documents/status-badge";
import { VisibilityBadge } from "@/components/documents/visibility-select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { User } from "@/lib/api/auth";
import { downloadFile } from "@/lib/api/download";
import { toastError } from "@/lib/api/errors";
import { extensionOf, type Document } from "@/lib/documents";
import { formatBytes, formatDateTime, formatRelative } from "@/lib/format";
import { useDeleteDocument } from "@/lib/hooks/use-documents";

const TYPE_ICON = { pdf: FileText, docx: FileType, pptx: Presentation, xlsx: FileSpreadsheet };

function FileIcon({ filename }: { filename: string }) {
  const Icon = TYPE_ICON[extensionOf(filename) as keyof typeof TYPE_ICON] ?? FileText;
  return <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />;
}

const canDelete = (doc: Document, user: User) => user.role === "admin" || doc.owner_id === user.id;
const ownerLabel = (doc: Document, user: User) =>
  doc.owner_id === user.id ? "You" : (doc.owner_name ?? "Former member");

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function sizeLine(doc: Document): string {
  const parts = [formatBytes(doc.size_bytes)];
  if (doc.page_count != null) parts.push(plural(doc.page_count, "page"));
  if (doc.chunk_count != null) parts.push(plural(doc.chunk_count, "chunk"));
  return parts.join(" · ");
}

export function DocumentsTable({ documents, user }: { documents: Document[]; user: User }) {
  const [toDelete, setToDelete] = useState<Document | null>(null);

  return (
    <>
      {/* Desktop / tablet: a table */}
      <div className="hidden overflow-hidden rounded-lg border bg-card md:block">
        <Table>
          <TableHeader className="bg-muted/60">
            <TableRow>
              <TableHead className="pl-4">Name</TableHead>
              <TableHead>Visible to</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="hidden lg:table-cell">Size</TableHead>
              <TableHead>Owner</TableHead>
              <TableHead>Uploaded</TableHead>
              <TableHead className="w-12 pr-4">
                <span className="sr-only">Actions</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.id}>
                <TableCell className="max-w-72 pl-4">
                  <div className="flex items-center gap-2.5">
                    <FileIcon filename={doc.filename} />
                    <span className="truncate font-medium" title={doc.filename}>
                      {doc.filename}
                    </span>
                    <Warnings warnings={doc.warnings} />
                  </div>
                </TableCell>
                <TableCell>
                  <VisibilityBadge visibility={doc.visibility} />
                </TableCell>
                <TableCell>
                  <StatusBadge status={doc.status} error={doc.error} />
                </TableCell>
                <TableCell className="hidden text-muted-foreground lg:table-cell">
                  {sizeLine(doc)}
                </TableCell>
                <TableCell className="max-w-40 truncate">{ownerLabel(doc, user)}</TableCell>
                <TableCell className="text-muted-foreground">
                  <time dateTime={doc.created_at} title={formatDateTime(doc.created_at)}>
                    {formatRelative(doc.created_at)}
                  </time>
                </TableCell>
                <TableCell className="pr-4 text-right">
                  <DocumentActions doc={doc} user={user} onDelete={() => setToDelete(doc)} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Phone: stacked cards */}
      <ul className="space-y-3 md:hidden" aria-label="Documents">
        {documents.map((doc) => (
          <li key={doc.id} className="rounded-lg border bg-card p-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5">
                <FileIcon filename={doc.filename} />
              </span>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <p className="truncate font-medium">{doc.filename}</p>
                  <Warnings warnings={doc.warnings} />
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <StatusBadge status={doc.status} error={doc.error} />
                  <VisibilityBadge visibility={doc.visibility} />
                </div>
                <p className="type-small text-muted-foreground">
                  {ownerLabel(doc, user)} · {formatRelative(doc.created_at)} · {sizeLine(doc)}
                </p>
                {doc.status === "failed" && doc.error && (
                  <p className="type-small text-destructive">{doc.error}</p>
                )}
              </div>
              <DocumentActions doc={doc} user={user} onDelete={() => setToDelete(doc)} />
            </div>
          </li>
        ))}
      </ul>

      <DeleteDialog doc={toDelete} onClose={() => setToDelete(null)} />
    </>
  );
}

function Warnings({ warnings }: { warnings: unknown[] }) {
  if (warnings.length === 0) return null;
  const text = warnings.map(String).join(" · ");
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="shrink-0 rounded-full text-warning"
          aria-label={`Warnings: ${text}`}
        >
          <Info className="size-4" aria-hidden />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">{text}</TooltipContent>
    </Tooltip>
  );
}

function DocumentActions({
  doc,
  user,
  onDelete,
}: {
  doc: Document;
  user: User;
  onDelete: () => void;
}) {
  const download = () =>
    downloadFile(`/documents/${doc.id}/download`, doc.filename).catch(toastError);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${doc.filename}`}>
          <Ellipsis />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuItem onSelect={download}>
          <Download /> Download
        </DropdownMenuItem>
        {/* Phase 5: POST insights → /history/[id] */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div>
              <DropdownMenuItem disabled>
                <Sparkles /> Get insights
              </DropdownMenuItem>
            </div>
          </TooltipTrigger>
          <TooltipContent side="left">Coming soon</TooltipContent>
        </Tooltip>
        {canDelete(doc, user) && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onSelect={onDelete}>
              <Trash2 /> Delete
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function DeleteDialog({ doc, onClose }: { doc: Document | null; onClose: () => void }) {
  const remove = useDeleteDocument();
  return (
    <AlertDialog open={doc !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this document?</AlertDialogTitle>
          <AlertDialogDescription>
            <span className="font-medium text-foreground">{doc?.filename}</span> will be removed for
            everyone, and the assistant will no longer answer from it.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={remove.isPending}
            onClick={(e) => {
              e.preventDefault(); // close only after the delete succeeded
              if (doc) remove.mutate(doc, { onSuccess: onClose });
            }}
          >
            {remove.isPending ? "Deleting…" : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
