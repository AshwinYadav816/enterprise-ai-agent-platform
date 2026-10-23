"use client";

import { useEffect, useState } from "react";

import { readStored, storageKey, writeStored, type StorageKind } from "@/lib/storage";
import { useAuth } from "@/providers/auth-provider";

/**
 * useState that survives a refresh (see lib/storage.ts). `parse` validates what was stored
 * (an older app version or a hand edit may have left anything there) and returns undefined to
 * fall back to `initial`. A value equal to `initial` removes the entry, so empty drafts don't
 * pile up. Only for components rendered after sign-in (they never render on the server).
 */
export function useStoredState<T>(
  kind: StorageKind,
  name: string,
  initial: T,
  parse: (value: unknown) => T | undefined,
): [T, React.Dispatch<React.SetStateAction<T>>] {
  const { user } = useAuth();
  const key = user ? storageKey(kind, user.id, name) : null;
  const [value, setValue] = useState<T>(() =>
    key ? (parse(readStored(key)) ?? initial) : initial,
  );

  useEffect(() => {
    if (!key) return;
    writeStored(key, JSON.stringify(value) === JSON.stringify(initial) ? undefined : value);
  }, [key, value, initial]);

  return [value, setValue];
}

/**
 * For forms that own their state (react-hook-form): read the saved draft once for the form's
 * defaults, then `useSaveDraft` writes the live values back.
 */
export function useRestoredDraft<T>(
  name: string,
  empty: T,
  parse: (value: unknown) => T | undefined,
): T {
  const { user } = useAuth();
  const [restored] = useState<T>(() =>
    user ? (parse(readStored(storageKey("draft", user.id, name))) ?? empty) : empty,
  );
  return restored;
}

export function useSaveDraft<T>(name: string, value: T, empty: T): void {
  const { user } = useAuth();
  const json = JSON.stringify(value);
  const emptyJson = JSON.stringify(empty);
  useEffect(() => {
    if (!user) return;
    writeStored(
      storageKey("draft", user.id, name),
      json === emptyJson ? undefined : JSON.parse(json),
    );
  }, [user, name, json, emptyJson]);
}
