import { expect, test } from "@playwright/test";

import { signIn, TINY_PDF, USERS } from "./helpers";

test("upload a document, wait until it's ready, then delete it", async ({ page }) => {
  const filename = `e2e-policy-${Date.now().toString(36)}.pdf`;
  await signIn(page, USERS.manager, "/documents");
  await expect(page.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();

  // Upload dialog: one bad file is refused, the PDF is queued
  await page.getByRole("button", { name: "Upload" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Upload documents" });
  await dialog.locator('input[type="file"]').setInputFiles([
    { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("plain text") },
    { name: filename, mimeType: "application/pdf", buffer: TINY_PDF },
  ]);
  await expect(dialog.getByText(".txt files aren't supported")).toBeVisible();
  await expect(dialog.getByText("Ready to upload")).toBeVisible();
  await dialog.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(dialog.getByText("Uploaded", { exact: false })).toBeVisible();
  await dialog.getByRole("button", { name: "Done" }).click();

  // processing → ready (the page polls; instant with the fake AI, longer with the real one)
  const row = page.getByRole("row").filter({ hasText: filename });
  await expect(row).toBeVisible();
  await expect(row.getByText("Ready")).toBeVisible({ timeout: 60_000 });
  await expect(row.getByText("You")).toBeVisible();

  // Clean up: delete with confirmation
  await page.getByRole("button", { name: `Actions for ${filename}` }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(row).toHaveCount(0);
});
