import { expect, test } from "@playwright/test";

import { signIn, USERS } from "./helpers";

test("chat streams a reply that is still there after a reload", async ({ page }) => {
  const question = `E2E question ${Date.now().toString(36)}`;
  await signIn(page, USERS.employee, "/chat");
  // Dev server only: compile the /chat/[id] route before the (fast, fake) reply starts.
  await page.goto("/chat/00000000-0000-0000-0000-000000000000");
  await expect(page.getByText("This conversation doesn't exist")).toBeVisible();
  await page.goto("/chat");
  await expect(
    page.getByRole("heading", { name: "What can I help you with today?" }),
  ).toBeVisible();

  const box = page.getByRole("textbox", { name: "Message" });
  await box.fill(question);
  await box.press("Enter");

  // The conversation gets its own URL and the answer streams in (coral cursor while streaming)
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);
  await expect(page.locator("[data-cursor]")).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop generating" })).toBeVisible();
  const answer = page.getByRole("article").last();
  await expect(answer).toContainText("fake answer"); // the backend's fake AI (AI_MODE=fake)
  await expect(page.locator("[data-cursor]")).toHaveCount(0);
  await expect(answer).toContainText("Used: Research");

  // Saved on the server: the same conversation after a reload
  const url = page.url();
  await page.reload();
  await expect(page).toHaveURL(url);
  await expect(page.getByText(question).first()).toBeVisible();
  await expect(page.getByRole("article").last()).toContainText("fake answer");

  // Clean up: delete the conversation from the list
  const item = page
    .getByRole("navigation", { name: "Conversations" })
    .locator('a[aria-current="page"]');
  await expect(item).toContainText(question);
  await page
    .getByRole("button", { name: `Options for ${question}` })
    .first()
    .click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page.getByRole("alertdialog").getByRole("button", { name: "Delete" }).click();
  await expect(page).toHaveURL(/\/chat$/);
});
