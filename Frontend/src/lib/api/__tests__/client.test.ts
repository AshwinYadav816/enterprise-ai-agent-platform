import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearToken, getToken, setOnAuthLost, setToken, type TokenResponse } from "@/lib/api/auth";
import { api } from "@/lib/api/client";
import { filenameFromDisposition } from "@/lib/api/download";
import { ApiError, unwrap } from "@/lib/api/errors";

const ME = {
  id: "u1",
  org_id: "o1",
  email: "ana@acme-demo.com",
  full_name: "Ana",
  role: "admin" as const,
  is_active: true,
  must_change_password: false,
  last_login_at: null,
  created_at: "2026-10-22T00:00:00Z",
};

function session(token: string): TokenResponse {
  return {
    access_token: token,
    token_type: "bearer",
    expires_in: 900,
    must_change_password: false,
    user: ME,
  };
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const unauthorized = () => json(401, { error: { code: "unauthorized", message: "Not signed in" } });

type Handler = (request: Request) => Response | Promise<Response>;

/** Stubs global fetch; records every request (method, path, auth header, body). */
function mockFetch(handler: Handler) {
  const calls: { method: string; path: string; auth: string | null; body: string }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    calls.push({
      method: request.method,
      path: new URL(request.url).pathname,
      auth: request.headers.get("Authorization"),
      body: await request.clone().text(),
    });
    return handler(request);
  });
  vi.stubGlobal("fetch", fetchMock);
  const count = (path: string) => calls.filter((c) => c.path === path).length;
  return { calls, count };
}

/** /users/me answers 200 only with `Bearer <valid>`; /auth/refresh hands out `next`. */
function backend({
  valid,
  next,
  refreshOk = true,
}: {
  valid: string;
  next: string;
  refreshOk?: boolean;
}) {
  return async (request: Request) => {
    const path = new URL(request.url).pathname;
    if (path === "/api/v1/auth/refresh") {
      await new Promise((r) => setTimeout(r, 20)); // keep the refresh in flight for a moment
      return refreshOk ? json(200, session(next)) : unauthorized();
    }
    if (request.headers.get("Authorization") !== `Bearer ${valid}`) return unauthorized();
    return json(200, ME);
  };
}

beforeEach(() => {
  clearToken();
  setOnAuthLost(null);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("adds the Bearer token and sends credentials", async () => {
    setToken("t1");
    const { calls } = mockFetch(() => json(200, ME));

    const me = unwrap(await api.GET("/api/v1/users/me"));

    expect(me.email).toBe(ME.email);
    expect(calls).toHaveLength(1);
    expect(calls[0]).toMatchObject({ path: "/api/v1/users/me", auth: "Bearer t1" });
  });

  it("on 401 refreshes once and retries the request with the new token", async () => {
    setToken("expired");
    const { calls, count } = mockFetch(backend({ valid: "fresh", next: "fresh" }));

    const me = unwrap(await api.GET("/api/v1/users/me"));

    expect(me.id).toBe("u1");
    expect(count("/api/v1/auth/refresh")).toBe(1);
    expect(calls.map((c) => [c.path, c.auth])).toEqual([
      ["/api/v1/users/me", "Bearer expired"],
      ["/api/v1/auth/refresh", null],
      ["/api/v1/users/me", "Bearer fresh"],
    ]);
    expect(getToken()).toBe("fresh");
  });

  it("shares one refresh between parallel 401s", async () => {
    setToken("expired");
    const { count } = mockFetch(backend({ valid: "fresh", next: "fresh" }));

    const results = await Promise.all([
      api.GET("/api/v1/users/me"),
      api.GET("/api/v1/users/me"),
      api.GET("/api/v1/users/me"),
    ]);

    expect(results.map((r) => r.response.status)).toEqual([200, 200, 200]);
    expect(count("/api/v1/auth/refresh")).toBe(1);
  });

  it("calls onAuthLost and clears the token when the refresh is rejected", async () => {
    setToken("expired");
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);
    const { count } = mockFetch(backend({ valid: "fresh", next: "fresh", refreshOk: false }));

    const result = await api.GET("/api/v1/users/me");

    expect(result.response.status).toBe(401);
    expect(() => unwrap(result)).toThrow(ApiError);
    expect(onAuthLost).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
    expect(count("/api/v1/users/me")).toBe(1); // no retry without a new token
  });

  it("does not refresh on a 401 from an auth endpoint (wrong password)", async () => {
    const { count } = mockFetch(() =>
      json(401, { error: { code: "invalid_credentials", message: "Wrong email or password" } }),
    );

    const result = await api.POST("/api/v1/auth/login", {
      body: { email: "ana@acme-demo.com", password: "nope" },
    });

    expect(count("/api/v1/auth/refresh")).toBe(0);
    expect(() => unwrap(result)).toThrow("Wrong email or password");
  });

  it("retries a POST with its original body", async () => {
    setToken("expired");
    const { calls } = mockFetch(async (request) => {
      const path = new URL(request.url).pathname;
      if (path === "/api/v1/auth/refresh") return json(200, session("fresh"));
      if (request.headers.get("Authorization") !== "Bearer fresh") return unauthorized();
      return json(201, { id: "c1", title: "Hi", created_at: "x", updated_at: "x" });
    });

    const result = await api.POST("/api/v1/conversations", { body: { title: "Hi" } });

    expect(result.response.status).toBe(201);
    const posts = calls.filter((c) => c.path === "/api/v1/conversations");
    expect(posts.map((c) => c.body)).toEqual(['{"title":"Hi"}', '{"title":"Hi"}']);
  });
});

describe("ApiError", () => {
  it("is parsed from the backend error body", async () => {
    setToken("t1");
    mockFetch(() =>
      json(409, {
        error: { code: "document_not_ready", message: "These documents are still processing" },
      }),
    );

    const result = await api.GET("/api/v1/users/me");

    let error: unknown;
    try {
      unwrap(result);
    } catch (e) {
      error = e;
    }
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "document_not_ready",
      message: "These documents are still processing",
    });
  });

  it("keeps validation details and survives non-JSON bodies", () => {
    const validation = ApiError.fromBody(422, {
      error: {
        code: "validation_error",
        message: "Invalid request",
        details: [{ field: "email", message: "value is not a valid email address" }],
      },
    });
    expect(validation.details).toEqual([
      { field: "email", message: "value is not a valid email address" },
    ]);

    const proxyPage = ApiError.fromBody(502, "<html>Bad gateway</html>");
    expect(proxyPage).toMatchObject({ status: 502, code: "http_502" });
    expect(proxyPage.message).toMatch(/something went wrong/i);
  });
});

describe("filenameFromDisposition", () => {
  it("prefers the UTF-8 filename and falls back to the plain one", () => {
    expect(
      filenameFromDisposition(
        `attachment; filename="report.pdf"; filename*=UTF-8''Q3%20r%C3%A9sum%C3%A9.pdf`,
      ),
    ).toBe("Q3 résumé.pdf");
    expect(filenameFromDisposition('attachment; filename="leave-policy.pdf"')).toBe(
      "leave-policy.pdf",
    );
    expect(filenameFromDisposition(null)).toBeNull();
  });
});
