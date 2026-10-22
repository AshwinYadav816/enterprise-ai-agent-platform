import { expect, test } from "@playwright/test";

import { adminApi, signIn, uniqueEmail, USERS } from "./helpers";

test("an admin creates a user and sees the temporary password once", async ({ page }) => {
  const email = uniqueEmail("e2e.added");
  await signIn(page, USERS.admin, "/admin/users");
  await expect(page.getByRole("heading", { name: "Users", level: 1 })).toBeVisible();

  try {
    await page.getByRole("button", { name: "Add user" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Full name").fill("E2E Added");
    await dialog.getByLabel("Work email").fill(email);
    await dialog.getByRole("button", { name: "Add user" }).click();

    // The one-time password, with the security note
    const password = dialog.getByLabel("Temporary password");
    await expect(password).toBeVisible();
    await expect(password).not.toBeEmpty();
    await expect(
      dialog.getByText("Share this securely; the user must change it on first login"),
    ).toBeVisible();
    await dialog.getByRole("button", { name: "Done" }).click();
    await expect(dialog).toHaveCount(0);

    // Listed, still on a temporary password; the dashboard counts them
    const row = page.getByRole("row").filter({ hasText: email });
    await expect(row).toContainText("E2E Added");
    await expect(row).toContainText("Temporary password");

    // Deactivate with confirmation (also the cleanup)
    await row.getByRole("button", { name: "Deactivate" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Deactivate" }).click();
    await expect(row).toContainText("Deactivated");
  } finally {
    // If the test failed half-way, don't leave an active test account behind.
    const admin = await adminApi();
    const user = await admin.findUser(email);
    if (user) await admin.deactivate(user.id);
    await admin.dispose();
  }
});
