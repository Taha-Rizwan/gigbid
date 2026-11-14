import { defineConfig, devices } from "@playwright/test";

/**
 * E2E specs mock every /api/** call (tests/e2e/mock-api.ts), so the FastAPI
 * backend does not need to be running.
 *
 * - Set E2E_BASE_URL to test an app that is already running (no webServer).
 * - Otherwise Playwright starts the standalone server on :3000 (run `npm run build` first),
 *   or reuses a server already listening there.
 */
const external = process.env.E2E_BASE_URL;
const baseURL = external ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: external
    ? undefined
    : {
        command: "npm run start:standalone",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
