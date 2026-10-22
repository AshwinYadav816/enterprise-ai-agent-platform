import { expect, request, type Page } from "@playwright/test";

/** Backend origin (the API calls below go straight to it, like the app in dev). */
export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8000";

/** Seed accounts (Backend/scripts/seed_demo.py). */
export const USERS = {
  admin: {
    email: process.env.E2E_ADMIN_EMAIL ?? "admin@acme-demo.com",
    password: process.env.E2E_ADMIN_PASSWORD ?? "Admin@Demo2026",
  },
  manager: {
    email: process.env.E2E_MANAGER_EMAIL ?? "manager@acme-demo.com",
    password: process.env.E2E_MANAGER_PASSWORD ?? "Manager@Demo2026",
  },
  employee: {
    email: process.env.E2E_EMPLOYEE_EMAIL ?? "employee@acme-demo.com",
    password: process.env.E2E_EMPLOYEE_PASSWORD ?? "Employee@Demo2026",
  },
};

/** A unique, valid address for users created by a test run. */
export const uniqueEmail = (name: string) => `${name}.${Date.now().toString(36)}@acme-demo.com`;

/** Sign in through the login form; lands on `next` (default /chat). */
export async function signIn(
  page: Page,
  user: { email: string; password: string },
  next = "/chat",
) {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(user.email);
  await page.getByLabel("Password", { exact: true }).fill(user.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`${next.replace(/\//g, "\\/")}`));
}

/**
 * Admin API session for setup and cleanup (creating / deactivating test users). It has its own
 * cookie jar, so it never touches the browser's session.
 */
export async function adminApi() {
  const api = await request.newContext({ baseURL: API_URL });
  const login = await api.post("/api/v1/auth/login", { data: USERS.admin });
  expect(login.ok(), await login.text()).toBeTruthy();
  const { access_token } = (await login.json()) as { access_token: string };
  const headers = { Authorization: `Bearer ${access_token}` };

  return {
    async createUser(fullName: string, email: string, role = "employee") {
      const res = await api.post("/api/v1/admin/users", {
        headers,
        data: { full_name: fullName, email, role },
      });
      expect(res.status(), await res.text()).toBe(201);
      return (await res.json()) as { user: { id: string }; temporary_password: string };
    },
    async deactivate(userId: string) {
      await api.patch(`/api/v1/admin/users/${userId}`, { headers, data: { is_active: false } });
    },
    async findUser(email: string) {
      const res = await api.get("/api/v1/admin/users", { headers, params: { search: email } });
      const body = (await res.json()) as { items: { id: string; email: string }[] };
      return body.items.find((u) => u.email === email);
    },
    async dispose() {
      await api.post("/api/v1/auth/logout");
      await api.dispose();
    },
  };
}

/** Smallest valid PDF (one empty page): enough for upload + fake-AI ingestion. */
export const TINY_PDF = Buffer.from(
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" +
    "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n" +
    "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n" +
    "trailer<</Root 1 0 R>>\n%%EOF\n",
);
