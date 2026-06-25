import { test as base, type Page } from "@playwright/test";

/**
 * Helpers et fixtures partagés par les tests E2E.
 *
 * Credentials de test injectés via env (jamais en clair dans le repo) :
 *   PORTAL_TEST_EMAIL    (default : jean.kamga@test.local)
 *   PORTAL_TEST_PASSWORD (default : test1234)
 */
export const PORTAL_EMAIL =
  process.env.PORTAL_TEST_EMAIL ?? "jean.kamga@test.local";
export const PORTAL_PASSWORD =
  process.env.PORTAL_TEST_PASSWORD ?? "test1234";

export type AuthedFixtures = { authedPage: Page };

export const test = base.extend<AuthedFixtures>({
  authedPage: async ({ page }, use) => {
    await page.goto("/fr/connexion");
    await page.getByLabel(/Adresse e-mail/i).fill(PORTAL_EMAIL);
    await page.getByLabel(/^Mot de passe$/i).fill(PORTAL_PASSWORD);
    await page.getByRole("button", { name: /Se connecter/i }).click();
    // Redirection attendue vers /fr (dashboard)
    await page.waitForURL((url) => !url.pathname.includes("/connexion"), {
      timeout: 15_000,
    });
    await use(page);
  },
});

export { expect } from "@playwright/test";
