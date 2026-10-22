import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGuard } from "@/components/layout/auth-guard";
import type { User } from "@/lib/api/auth";

const replace = vi.fn();
let pathname = "/documents";
let auth: { user: User | null; status: "loading" | "authenticated" | "anonymous" };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => pathname,
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/providers/auth-provider", () => ({ useAuth: () => auth }));

function user(overrides: Partial<User> = {}): User {
  return {
    id: "u1",
    org_id: "o1",
    email: "eli@acme-demo.com",
    full_name: "Eli",
    role: "employee",
    is_active: true,
    must_change_password: false,
    last_login_at: null,
    created_at: "2026-10-22T00:00:00Z",
    ...overrides,
  };
}

const renderGuard = (props: { adminOnly?: boolean; allowPasswordChange?: boolean } = {}) =>
  render(
    <AuthGuard {...props} fallback={<p>loading</p>}>
      <p>secret page</p>
    </AuthGuard>,
  );

beforeEach(() => {
  replace.mockClear();
  pathname = "/documents";
});

describe("AuthGuard", () => {
  it("shows the fallback, not the page or a redirect, while the session loads", () => {
    auth = { user: null, status: "loading" };
    renderGuard();
    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("sends anonymous visitors to login with next", () => {
    auth = { user: null, status: "anonymous" };
    renderGuard();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fdocuments");
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });

  it("forces the password change for temporary passwords", () => {
    auth = { user: user({ must_change_password: true }), status: "authenticated" };
    renderGuard();
    expect(replace).toHaveBeenCalledWith("/change-password?next=%2Fdocuments");
  });

  it("lets the change page render for temporary passwords", () => {
    auth = { user: user({ must_change_password: true }), status: "authenticated" };
    renderGuard({ allowPasswordChange: true });
    expect(screen.getByText("secret page")).toBeInTheDocument();
  });

  it("redirects non-admins away from admin pages", () => {
    pathname = "/admin";
    auth = { user: user({ role: "manager" }), status: "authenticated" };
    renderGuard({ adminOnly: true });
    expect(replace).toHaveBeenCalledWith("/chat");
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });

  it("renders the page for an allowed user", () => {
    auth = { user: user({ role: "admin" }), status: "authenticated" };
    renderGuard({ adminOnly: true });
    expect(screen.getByText("secret page")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
