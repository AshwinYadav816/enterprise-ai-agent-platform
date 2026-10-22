import { API_BASE, authFetch } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/errors";

/**
 * Download a protected file. A plain `<a href>` can't send the Bearer token, so: fetch with auth
 * (same refresh-and-retry as the API client) → blob → temporary object URL → click → revoke.
 *
 * @param path API path after /api/v1, e.g. `/documents/${id}/download`
 * @param fallbackName used when the response has no Content-Disposition filename
 */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await authFetch(new Request(`${API_BASE}${path}`, { credentials: "include" }));
  if (!response.ok) throw await ApiError.fromResponse(response);

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download =
      filenameFromDisposition(response.headers.get("Content-Disposition")) ?? fallbackName;
    document.body.append(link);
    link.click();
    link.remove();
  } finally {
    // Revoke after the click has been handled, or some browsers cancel the download.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

/** `filename*=UTF-8''…` (RFC 5987, preferred) or `filename="…"`. */
export function filenameFromDisposition(header: string | null): string | null {
  if (!header) return null;
  const extended = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      // malformed encoding: fall through to the plain filename
    }
  }
  const plain = /filename\s*=\s*"([^"]*)"|filename\s*=\s*([^;]+)/.exec(header);
  const name = plain?.[1] ?? plain?.[2]?.trim();
  return name || null;
}
