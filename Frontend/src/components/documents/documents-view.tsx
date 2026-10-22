"use client";

import { FileText, Loader2, Search, Upload } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { PageHeader } from "@/components/common/page-header";
import { DocumentsTable } from "@/components/documents/documents-table";
import { UploadDialog } from "@/components/documents/upload-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { STATUS_LABEL, type DocumentStatus } from "@/lib/documents";
import { useDocuments } from "@/lib/hooks/use-documents";
import { useAuth } from "@/providers/auth-provider";

type StatusFilter = DocumentStatus | "all";

export function DocumentsView() {
  const { user } = useAuth();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");

  // Search as you type, without a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchText.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  const query = useDocuments({ search, status: status === "all" ? undefined : status });
  const filtered = search !== "" || status !== "all";

  const uploadButton = (
    <Button onClick={() => setUploadOpen(true)}>
      <Upload /> Upload
    </Button>
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Knowledge base"
        title="Documents"
        description="Files your team can ask questions about. Each one is visible to the roles you choose."
        actions={uploadButton}
      />

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <Input
            type="search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search by file name"
            aria-label="Search documents by file name"
            className="pl-9"
          />
        </div>
        <Select value={status} onValueChange={(v) => setStatus(v as StatusFilter)}>
          <SelectTrigger className="w-full sm:w-44" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {(Object.keys(STATUS_LABEL) as DocumentStatus[]).map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_LABEL[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {query.isPending ? (
        <TableSkeleton />
      ) : query.isError ? (
        <ErrorState
          title="Couldn't load documents"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : query.documents.length === 0 ? (
        filtered ? (
          <EmptyState
            icon={Search}
            title="No documents match"
            description="Try a different name or status."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setSearchText("");
                  setSearch("");
                  setStatus("all");
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={FileText}
            title="Your knowledge base is empty"
            description="Upload PDFs, Word, PowerPoint or Excel files and ask questions about them in chat."
            action={uploadButton}
          />
        )
      ) : (
        user && (
          <div className="space-y-4">
            <DocumentsTable documents={query.documents} user={user} />
            {query.hasNextPage && (
              <div className="flex justify-center">
                <Button
                  variant="outline"
                  onClick={() => void query.fetchNextPage()}
                  disabled={query.isFetchingNextPage}
                >
                  {query.isFetchingNextPage && <Loader2 className="animate-spin" aria-hidden />}
                  Load more
                </Button>
              </div>
            )}
          </div>
        )
      )}

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="space-y-2 rounded-lg border bg-card p-4" aria-busy="true">
      <span className="sr-only" role="status">
        Loading documents…
      </span>
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
