import type { components } from "@/lib/api/schema";

export type TokenResponse = components["schemas"]["TokenResponse"];
export type User = components["schemas"]["UserOut"];

/** Backend origin; empty = same origin (production behind Nginx routing /api). */
export const API_ORIGIN = process.env.NEXT_PUBLIC_API_URL ?? "";
export const API_BASE = `${API_ORIGIN}/api/v1`;

// ---- access token: memory only (never localStorage); the httpOnly refresh cookie survives reloads

let accessToken: string | null = null;

export function getToken(): string | null {
  return accessToken;
}

export function setToken(token: string): void {
  accessToken = token;
}

export function clearToken(): void {
  accessToken = null;
}

// ---- session listeners: the auth provider keeps its user in sync with every refresh

type SessionListener = (session: TokenResponse) => void;
const sessionListeners = new Set<SessionListener>();

export function onSession(listener: SessionListener): () => void {
  sessionListeners.add(listener);
  return () => sessionListeners.delete(listener);
}

/** Store a new session (login, register, refresh) and notify listeners. */
export function applySession(session: TokenResponse): void {
  setToken(session.access_token);
  sessionListeners.forEach((listener) => listener(session));
}

// ---- auth lost: called when a refresh is rejected (expired, revoked, user deactivated)

let authLostHandler: (() => void) | null = null;

export function setOnAuthLost(handler: (() => void) | null): void {
  authLostHandler = handler;
}

export function handleAuthLost(): void {
  clearToken();
  authLostHandler?.();
}

// ---- refresh

/**
 * The backend rotates the refresh cookie on every refresh and treats a reused cookie as theft
 * (it revokes ALL of the user's sessions). So refreshes must never overlap:
 *  - in this tab, concurrent callers share one in-flight promise;
 *  - across tabs, the Web Locks API runs them one at a time, so each tab presents the current
 *    cookie (the browser's cookie jar is shared, and updated before the lock is released).
 */
let inFlight: Promise<TokenResponse | null> | null = null;

const REFRESH_LOCK = "eap-auth-refresh";

async function postRefresh(): Promise<TokenResponse | null> {
  const response = await globalThis.fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) return null; // 401: no cookie, expired, revoked or reused
  const session = (await response.json()) as TokenResponse;
  applySession(session);
  return session;
}

/**
 * Exchange the refresh cookie for a new access token. Resolves to the new session, or `null`
 * when the server rejected the cookie (the caller decides whether that means "logged out").
 * Network errors reject, so an unreachable backend is not mistaken for a logout.
 */
export function refreshAccessToken(): Promise<TokenResponse | null> {
  if (!inFlight) {
    inFlight = refreshExclusive().finally(() => {
      inFlight = null;
    });
  }
  return inFlight;
}

async function refreshExclusive(): Promise<TokenResponse | null> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  if (!locks) return postRefresh(); // old browsers, tests
  return locks.request(REFRESH_LOCK, postRefresh);
}

// ---- authenticated fetch (API client, downloads, and later the chat stream)

const AUTH_PATH = /\/api\/v1\/auth\//;

/**
 * fetch() with the Bearer token. On a 401 from a non-auth endpoint it refreshes once and retries
 * the request once; if the refresh is rejected, the session is cleared and onAuthLost fires, and
 * the original 401 response is returned.
 */
export async function authFetch(request: Request): Promise<Response> {
  const retry = request.clone(); // the body of `request` is consumed by the first attempt
  const response = await globalThis.fetch(withToken(request));
  if (response.status !== 401 || AUTH_PATH.test(new URL(request.url, "http://x").pathname)) {
    return response;
  }
  const session = await refreshAccessToken();
  if (!session) {
    handleAuthLost();
    return response;
  }
  return globalThis.fetch(withToken(retry));
}

function withToken(request: Request): Request {
  const token = getToken();
  if (!token) return request;
  const headers = new Headers(request.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return new Request(request, { headers });
}
