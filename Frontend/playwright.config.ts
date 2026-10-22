import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real stack: the backend must be running with AI_MODE=fake
 * (see ../Backend/README.md); the frontend dev server is started here unless already running.
 *
 *   npx playwright test            # all flows
 *   npx playwright test --ui       # watch them run
 *
 * Accounts come from the backend seed (scripts/seed_demo.py); override with E2E_* env vars.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // One worker: the flows share the demo accounts and the login rate limit (5/min per account).
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chrome",
      // Locally: the installed Google Chrome (no browser download). CI: `npx playwright install chromium`.
      use: { ...devices["Desktop Chrome"], channel: process.env.CI ? undefined : "chrome" },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: `${baseURL}/login`,
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
