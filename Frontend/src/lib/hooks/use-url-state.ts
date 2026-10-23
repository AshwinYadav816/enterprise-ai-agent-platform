"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

/**
 * A page filter kept in the URL (?key=value): it survives a refresh, works with Back, and a
 * copied link opens the same view. The default value is left out of the URL. `allowed` rejects
 * hand-edited values (they fall back to the default).
 */
export function useUrlState<T extends string>(
  key: string,
  defaultValue: T,
  allowed?: readonly T[],
): [T, (value: T) => void] {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  const raw = params.get(key);
  const value =
    raw !== null && (!allowed || allowed.includes(raw as T)) ? (raw as T) : defaultValue;

  const setValue = useCallback(
    (next: T) => {
      // Read the live URL, not a render-time copy: two filters may change in the same tick.
      const current = new URLSearchParams(window.location.search);
      if (next === defaultValue || next === "") current.delete(key);
      else current.set(key, next);
      const query = current.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [key, defaultValue, pathname, router],
  );

  return [value, setValue];
}

/**
 * A search box kept in the URL (?q=…): `text` follows every keystroke, `search` (what to query
 * with) follows 300 ms after typing stops, so there's no request or history churn per key.
 */
export function useUrlSearch(key = "q"): {
  text: string;
  setText: (text: string) => void;
  search: string;
} {
  const [search, setSearch] = useUrlState<string>(key, "");
  const [text, setText] = useState(search);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (text.trim() !== search) setSearch(text.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [text, search, setSearch]);

  return { text, setText, search };
}
