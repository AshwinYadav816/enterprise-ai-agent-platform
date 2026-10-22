import { expect, test } from "@playwright/test";

import { adminApi, signIn, uniqueEmail } from "./helpers";

test("a new user signs in with a temporary password and must change it", async ({ page }) => {
  const admin = await adminApi();
  const email = uniqueEmail("e2e.newcomer");
  const { user, temporary_password } = await admin.createUser("E2E Newcomer", email);

  try {
    // Trying to open a page first: the login keeps it as ?next=
    await page.goto("/documents");
    await expect(page).toHaveURL(/\/login\?next=%2Fdocuments/);

    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password", { exact: true }).fill(temporary_password);
    await page.getByRole("button", { name: "Sign in" }).click();

    // Forced password change, and no way around it
    await expect(page).toHaveURL(/\/change-password/);
    await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
    await page.goto("/chat");
    await expect(page).toHaveURL(/\/change-password/);

    await page.getByLabel("Temporary password").fill(temporary_password);
    await page.getByLabel("New password", { exact: true }).fill("E2eNewcomer123");
    await page.getByLabel("Confirm new password").fill("E2eNewcomer123");
    await page.getByRole("button", { name: "Save password" }).click();

    // In the app, as an employee (no Admin section); a reload keeps the session
    await expect(page).toHaveURL(/\/chat/);
    await expect(page.getByRole("button", { name: /Account menu for E2E Newcomer/ })).toBeVisible();
    await expect(page.getByRole("list", { name: "Admin" })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole("button", { name: /Account menu for E2E Newcomer/ })).toBeVisible();

    // The new password works on its own
    await page.getByRole("button", { name: /Account menu/ }).click();
    await page.getByRole("menuitem", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login/);
    await signIn(page, { email, password: "E2eNewcomer123" });
  } finally {
    await admin.deactivate(user.id);
    await admin.dispose();
  }
});
