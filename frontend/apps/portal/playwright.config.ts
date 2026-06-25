import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — tests E2E du portail membre.
 *
 * - En CI : pointe sur la prod par défaut (`PORTAL_BASE_URL` override possible).
 * - En local : `pnpm e2e` ou `npm run e2e` (assure-toi que le portail tourne
 *   sur localhost:3201, ou override BASE_URL).
 *
 * Les credentials de test sont injectés via env vars (cf. e2e/fixtures.ts).
 */

const BASE_URL =
  process.env.PORTAL_BASE_URL ??
  "https://portail.gathe-finance.horus-lab.com";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  timeout: 30_000,
  expect: { timeout: 7_500 },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "fr-FR",
    timezoneId: "Africa/Douala",
  },

  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
});
