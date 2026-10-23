/**
 * Per-user state kept in this browser (localStorage), so a refresh restores what the user was
 * doing. Two kinds:
 * - drafts: unsent work (chat composer, tool forms). Removed on sign-out.
 * - prefs: small UI choices (collapsed sidebar, upload visibility). Kept across sign-ins.
 * Keys include the user id, so people sharing a browser never see each other's drafts.
 * Storage can be unavailable (private mode, blocked, full): every access is best effort.
 */

export type StorageKind = "draft" | "pref";

const PREFIX = "eap:";

export function storageKey(kind: StorageKind, userId: string, name: string): string {
  return `${PREFIX}${kind}:${userId}:${name}`;
}

export function readStored(key: string): unknown {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? undefined : (JSON.parse(raw) as unknown);
  } catch {
    return undefined;
  }
}

/** `undefined` removes the entry. */
export function writeStored(key: string, value: unknown): void {
  try {
    if (value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // full or blocked: the draft just won't survive a refresh
  }
}

/** Remove every draft (all users) from this browser: on sign-out. */
export function clearDrafts(): void {
  try {
    const storage = window.localStorage;
    const drafts = Object.keys(storage).filter((k) => k.startsWith(`${PREFIX}draft:`));
    for (const key of drafts) storage.removeItem(key);
  } catch {
    // nothing to clear
  }
}

// --- parsers: validate what was stored (an older version or a hand edit may have left anything)

export const asString = (v: unknown) => (typeof v === "string" ? v : undefined);
export const asBoolean = (v: unknown) => (typeof v === "boolean" ? v : undefined);

export function asOneOf<T extends string>(allowed: readonly T[]) {
  return (v: unknown) => (allowed.includes(v as T) ? (v as T) : undefined);
}

/** A record whose fields are each checked by their own parser (missing fields: undefined). */
export function asRecord<T extends object>(fields: {
  [K in keyof T]: (v: unknown) => T[K] | undefined;
}) {
  return (v: unknown): T | undefined => {
    if (typeof v !== "object" || v === null) return undefined;
    const out = {} as T;
    for (const name of Object.keys(fields) as (keyof T)[]) {
      const parsed = fields[name]((v as Record<keyof T, unknown>)[name]);
      if (parsed === undefined) return undefined;
      out[name] = parsed;
    }
    return out;
  };
}
