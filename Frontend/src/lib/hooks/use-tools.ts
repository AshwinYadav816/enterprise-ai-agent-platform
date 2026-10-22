"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { API_BASE, authFetch } from "@/lib/api/auth";
import { api } from "@/lib/api/client";
import { ApiError, unwrap } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";
import type { components } from "@/lib/api/schema";
import type { ResultData } from "@/lib/chat/types";

export type Generation = components["schemas"]["GenerationOut"];
export type GenerationSummary = components["schemas"]["GenerationSummary"];
export type GenerationKind = components["schemas"]["GenerationKind"];
export type ReportRequest = components["schemas"]["ReportRequest"];
export type EmailRequest = components["schemas"]["EmailRequest"];
export type ReportType = ReportRequest["report_type"];
export type EmailTask = EmailRequest["task"];
export type EmailTone = NonNullable<EmailRequest["tone"]>;

export const KIND_LABEL: Record<GenerationKind, string> = {
  meeting: "Meeting summary",
  report: "Report",
  email: "Email",
  document_insights: "Document insights",
};

/** A saved generation in the shape the chat result cards render. */
export function generationResult(g: Pick<Generation, "kind" | "output" | "markdown">): ResultData {
  const agent = g.kind === "document_insights" ? "document" : g.kind;
  return { agent, output: g.output, markdown: g.markdown ?? undefined };
}

export const generationPdfPath = (id: string) => `/tools/generations/${id}/pdf`;

/** Tool results show their own error in the result panel instead of a toast. */
function useToolMutation<TInput>(run: (input: TInput) => Promise<Generation>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: run,
    meta: { silentError: true },
    onSuccess: (generation) => {
      queryClient.setQueryData(keys.generations.detail(generation.id), generation);
      return queryClient.invalidateQueries({ queryKey: keys.generations.all });
    },
  });
}

export type MeetingInput = { title?: string } & (
  { transcript: string; file?: never } | { file: File; transcript?: never }
);

export function useMeetingSummary() {
  return useToolMutation(async (input: MeetingInput): Promise<Generation> => {
    const title = input.title?.trim() || undefined;
    if (input.file) {
      // Multipart upload (.txt, .vtt, .docx); the typed client only does JSON.
      const form = new FormData();
      form.append("file", input.file);
      if (title) form.append("title", title);
      const response = await authFetch(
        new Request(`${API_BASE}/tools/meetings`, {
          method: "POST",
          body: form,
          credentials: "include",
        }),
      );
      if (!response.ok) throw await ApiError.fromResponse(response);
      return (await response.json()) as Generation;
    }
    return unwrap(
      await api.POST("/api/v1/tools/meetings", {
        body: { transcript: input.transcript ?? "", title },
      }),
    ) as Generation;
  });
}

export function useReport() {
  return useToolMutation(async (body: ReportRequest) =>
    unwrap(await api.POST("/api/v1/tools/reports", { body })),
  );
}

export function useEmail() {
  return useToolMutation(async (body: EmailRequest) =>
    unwrap(await api.POST("/api/v1/tools/emails", { body })),
  );
}

export function useDocumentInsights() {
  return useToolMutation(async (documentId: string) =>
    unwrap(
      await api.POST("/api/v1/tools/documents/{document_id}/insights", {
        params: { path: { document_id: documentId } },
      }),
    ),
  );
}

export function useGenerations(kind?: GenerationKind) {
  const query = useInfiniteQuery({
    queryKey: keys.generations.list({ kind }),
    queryFn: async ({ pageParam }) =>
      unwrap(
        await api.GET("/api/v1/tools/generations", {
          params: { query: { kind, cursor: pageParam, limit: 20 } },
        }),
      ),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const generations = useMemo(
    () => query.data?.pages.flatMap((page) => page.items) ?? [],
    [query.data],
  );
  return { ...query, generations };
}

export function useGeneration(id: string) {
  return useQuery({
    queryKey: keys.generations.detail(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/tools/generations/{generation_id}", {
          params: { path: { generation_id: id } },
        }),
      ),
    staleTime: Infinity, // generations never change
  });
}
