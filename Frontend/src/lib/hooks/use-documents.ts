"use client";

import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { toast } from "sonner";

import { API_BASE, authFetch } from "@/lib/api/auth";
import { api } from "@/lib/api/client";
import { ApiError, unwrap } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import type { Document, DocumentStatus, UserRole } from "@/lib/documents";

const POLL_MS = 3000;
const PAGE_SIZE = 20;

export type DocumentFilters = { search?: string; status?: DocumentStatus };

/**
 * Documents visible to the user, newest first, with "Load more" pages. While any loaded document
 * is still processing, refetches every 3 s (and stops as soon as none is), and toasts when one
 * becomes ready or fails.
 */
export function useDocuments(filters: DocumentFilters) {
  const search = filters.search?.trim() || undefined;
  const status = filters.status;

  const query = useInfiniteQuery({
    queryKey: keys.documents.list({ search, status }),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/documents", {
          params: { query: { search, status, cursor: pageParam, limit: PAGE_SIZE } },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    refetchInterval: (q) =>
      q.state.data?.pages.some((page) => page.items.some((d) => d.status === "processing"))
        ? POLL_MS
        : false,
  });

  const documents = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );
  useStatusToasts(documents);
  return { ...query, documents };
}

/** Toast once when a document this page has seen as `processing` turns ready or failed. */
function useStatusToasts(documents: Document[]) {
  const seen = useRef(new Map<string, DocumentStatus>());
  useEffect(() => {
    for (const doc of documents) {
      const before = seen.current.get(doc.id);
      if (before === "processing" && doc.status === "ready") {
        toast.success(`${doc.filename} is ready`, {
          description: "You can now ask questions about it.",
        });
      } else if (before === "processing" && doc.status === "failed") {
        toast.error(`${doc.filename} couldn't be processed`, {
          description: doc.error ?? undefined,
        });
      }
      seen.current.set(doc.id, doc.status);
    }
  }, [documents]);
}

/** Multipart upload (the typed client is JSON-first): returns the new `processing` document. */
export async function uploadDocument(file: File, visibility: UserRole): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  form.append("visibility", visibility);
  const response = await authFetch(
    new Request(`${API_BASE}/documents`, { method: "POST", body: form, credentials: "include" }),
  );
  if (!response.ok) throw await ApiError.fromResponse(response);
  return (await response.json()) as Document;
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, visibility }: { file: File; visibility: UserRole }) =>
      uploadDocument(file, visibility),
    meta: { silentError: true }, // the upload dialog shows the error next to the file
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.documents.all }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (doc: Pick<Document, "id" | "filename">) => {
      unwrap(
        await api.DELETE("/api/v1/documents/{document_id}", {
          params: { path: { document_id: doc.id } },
        }),
      );
      return doc;
    },
    onSuccess: (doc) => {
      toast.success(`Deleted ${doc.filename}`);
      return queryClient.invalidateQueries({ queryKey: keys.documents.all });
    },
  });
}
