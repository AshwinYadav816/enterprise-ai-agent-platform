import type { User } from "@/lib/api/auth";

export const HOME_PATH = "/chat";
export const CHANGE_PASSWORD_PATH = "/change-password";

/**
 * A `?next=` value we may navigate to: same-site paths only ("/documents?x=1"), never another
 * origin ("//evil.com", "https://…", "/\evil.com") and never back to an auth page.
 */
export function safeNext(next: string | null | undefined): string | null {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) {
    return null;
  }
  if (/^\/(login|register|change-password)(\/|\?|$)/.test(next)) return null;
  return next;
}

/** Where a signed-in user goes from an auth page. */
export function postLoginPath(user: Pick<User, "must_change_password">, next?: string | null) {
  if (user.must_change_password) {
    const target = safeNext(next);
    return target
      ? `${CHANGE_PASSWORD_PATH}?next=${encodeURIComponent(target)}`
      : CHANGE_PASSWORD_PATH;
  }
  return safeNext(next) ?? HOME_PATH;
}

export function loginPath(next?: string | null): string {
  const target = safeNext(next);
  return target && target !== HOME_PATH ? `/login?next=${encodeURIComponent(target)}` : "/login";
}
