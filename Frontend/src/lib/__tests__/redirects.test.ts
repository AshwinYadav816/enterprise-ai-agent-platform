import { describe, expect, it } from "vitest";

import { loginPath, postLoginPath, safeNext } from "@/lib/redirects";

describe("safeNext", () => {
  it("keeps same-site paths", () => {
    expect(safeNext("/documents")).toBe("/documents");
    expect(safeNext("/chat/abc?x=1")).toBe("/chat/abc?x=1");
  });

  it("rejects other origins and auth pages (no open redirect, no loops)", () => {
    for (const bad of ["https://evil.com", "//evil.com", "/\\evil.com", "evil", "", null]) {
      expect(safeNext(bad)).toBeNull();
    }
    expect(safeNext("/login")).toBeNull();
    expect(safeNext("/change-password?next=/x")).toBeNull();
    expect(safeNext("/registered-users")).toBe("/registered-users");
  });
});

describe("postLoginPath / loginPath", () => {
  it("sends temporary-password users to the change page, keeping next", () => {
    expect(postLoginPath({ must_change_password: true }, "/documents")).toBe(
      "/change-password?next=%2Fdocuments",
    );
    expect(postLoginPath({ must_change_password: false }, "/documents")).toBe("/documents");
    expect(postLoginPath({ must_change_password: false }, "//evil.com")).toBe("/chat");
  });

  it("builds the login URL", () => {
    expect(loginPath("/admin/users")).toBe("/login?next=%2Fadmin%2Fusers");
    expect(loginPath("/chat")).toBe("/login");
  });
});
