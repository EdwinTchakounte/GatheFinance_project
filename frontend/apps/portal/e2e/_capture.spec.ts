import { test } from "@playwright/test";

const PAGES = [
  { name: "connexion", path: "/fr/connexion" },
  { name: "carnet", path: "/fr/carnet" },
  { name: "profil", path: "/fr/profil" },
  { name: "credit-remboursement", path: "/fr/credit/remboursement" },
  { name: "credit-reconduction", path: "/fr/credit/reconduction" },
  { name: "epargne-depot-savings", path: "/fr/epargne/depot?context=savings" },
];

for (const p of PAGES) {
  test(`capture ${p.name}`, async ({ page }, testInfo) => {
    await page.goto(p.path);
    await page.waitForLoadState("networkidle");
    await page.screenshot({
      path: `audit-captures/${p.name}-${testInfo.project.name}.png`,
      fullPage: true,
    });
  });
}
