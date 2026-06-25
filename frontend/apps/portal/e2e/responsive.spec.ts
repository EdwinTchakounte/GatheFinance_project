import { test, expect } from "./fixtures";

/**
 * Tests responsive — vérifie que les pages clés ne débordent pas en
 * viewport mobile (Pixel 7 = 412×915). Le projet `mobile-chromium` du
 * playwright.config s'occupe automatiquement de fixer le viewport.
 */

const KEY_PATHS = [
  "/fr/connexion",
  "/fr",
  "/fr/carnet",
  "/fr/profil",
  "/fr/credit",
  "/fr/credit/remboursement",
  "/fr/credit/reconduction",
  "/fr/epargne/depot?context=savings",
];

test.describe("Responsive — pas de scroll horizontal", () => {
  for (const path of KEY_PATHS) {
    test(`${path} — pas d'overflow horizontal`, async ({ authedPage }) => {
      await authedPage.goto(path);
      // Laisse le temps au layout de poser ses repères + à éventuelle
      // redirection client de jouer.
      await authedPage.waitForLoadState("networkidle");
      const { docW, viewportW } = await authedPage.evaluate(() => ({
        docW: document.documentElement.scrollWidth,
        viewportW: window.innerWidth,
      }));
      // Tolérance 2px (scrollbars exotiques).
      expect(docW).toBeLessThanOrEqual(viewportW + 2);
    });
  }
});
