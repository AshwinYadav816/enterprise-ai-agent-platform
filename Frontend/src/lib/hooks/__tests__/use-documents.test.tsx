import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setToken } from "@/lib/api/auth";
import type { Document, DocumentStatus } from "@/lib/documents";
import { useDocuments } from "@/lib/hooks/use-documents";

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

function doc(status: DocumentStatus, error: string | null = null): Document {
  return {
    id: "d1",
    owner_id: "u1",
    owner_name: "Mina",
    filename: "plan.pdf",
    content_type: "application/pdf",
    size_bytes: 1000,
    allowed_roles: ["employee"],
    status,
    chunk_count: status === "ready" ? 3 : null,
    page_count: status === "ready" ? 2 : null,
    warnings: [],
    error,
    created_at: "2026-10-22T12:00:00Z",
    updated_at: "2026-10-22T12:00:00Z",
    visibility: "employee",
  };
}

/** GET /documents answers with the next status in `sequence` (the last one repeats). */
function serveStatuses(sequence: Document[]) {
  let call = 0;
  const fetchMock = vi.fn(async () => {
    const item = sequence[Math.min(call++, sequence.length - 1)];
    return new Response(JSON.stringify({ items: [item], next_cursor: null }), {
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  setToken("t");
  toast.success.mockClear();
  toast.error.mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useDocuments polling", () => {
  it("polls every 3 s while processing, toasts once when ready, then stops", async () => {
    const fetchMock = serveStatuses([doc("processing"), doc("processing"), doc("ready")]);
    const { result } = renderHook(() => useDocuments({}), { wrapper });
    await waitFor(() => expect(result.current.documents[0]?.status).toBe("processing"));

    await act(() => vi.advanceTimersByTimeAsync(3000));
    await act(() => vi.advanceTimersByTimeAsync(3000));
    await waitFor(() => expect(result.current.documents[0]?.status).toBe("ready"));
    expect(toast.success).toHaveBeenCalledTimes(1);
    expect(toast.success).toHaveBeenCalledWith("plan.pdf is ready", expect.anything());

    const callsWhenReady = fetchMock.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(fetchMock.mock.calls.length).toBe(callsWhenReady); // nothing processing: no polling
    expect(toast.success).toHaveBeenCalledTimes(1);
  });

  it("toasts the error when processing fails", async () => {
    serveStatuses([doc("processing"), doc("failed", "This PDF is password-protected.")]);
    const { result } = renderHook(() => useDocuments({}), { wrapper });
    await waitFor(() => expect(result.current.documents[0]?.status).toBe("processing"));

    await act(() => vi.advanceTimersByTimeAsync(3000));
    await waitFor(() => expect(result.current.documents[0]?.status).toBe("failed"));
    expect(toast.error).toHaveBeenCalledWith("plan.pdf couldn't be processed", {
      description: "This PDF is password-protected.",
    });
  });

  it("does not toast for documents that were already ready when the page opened", async () => {
    const fetchMock = serveStatuses([doc("ready")]);
    const { result } = renderHook(() => useDocuments({}), { wrapper });
    await waitFor(() => expect(result.current.documents).toHaveLength(1));
    await act(() => vi.advanceTimersByTimeAsync(10_000));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(toast.success).not.toHaveBeenCalled();
  });
});
