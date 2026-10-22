import type { components } from "@/lib/api/schema";

export type Document = components["schemas"]["DocumentOut"];
export type DocumentStatus = components["schemas"]["DocumentStatus"];
export type UserRole = components["schemas"]["UserRole"];

/** Mirrors the backend: pdf, docx, pptx, xlsx up to MAX_UPLOAD_MB (default 25, binary MB). */
export const ALLOWED_EXTENSIONS = ["pdf", "docx", "pptx", "xlsx"] as const;
export const MAX_UPLOAD_MB = 25;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
export const ACCEPT_ATTRIBUTE = ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(",");

export function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot > 0 ? filename.slice(dot + 1).toLowerCase() : "";
}

/** null when the file can be uploaded, else a message to show next to it. */
export function validateFile(file: Pick<File, "name" | "size">): string | null {
  const ext = extensionOf(file.name);
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) {
    return ext
      ? `.${ext} files aren't supported. Use PDF, Word, PowerPoint or Excel.`
      : "This file has no extension. Use PDF, Word, PowerPoint or Excel.";
  }
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_UPLOAD_BYTES) return `This file is larger than ${MAX_UPLOAD_MB} MB.`;
  return null;
}

// ---- roles and visibility (a document is visible to its role and every role above it)

export const ROLE_ORDER: UserRole[] = ["employee", "manager", "admin"];

export const VISIBILITY_LABEL: Record<UserRole, string> = {
  employee: "Everyone",
  manager: "Managers & admins",
  admin: "Admins only",
};

/** The visibility levels this user may pick: their own role and below. */
export function visibilityOptions(role: UserRole): UserRole[] {
  return ROLE_ORDER.slice(0, ROLE_ORDER.indexOf(role) + 1);
}

export const STATUS_LABEL: Record<DocumentStatus, string> = {
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};
