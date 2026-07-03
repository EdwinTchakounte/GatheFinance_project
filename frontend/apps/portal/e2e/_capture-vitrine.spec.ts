import { test } from "@playwright/test";

const VITRINE = process.env.VITRINE_BASE_URL ?? "https://gathe-finance.horus-lab.com";

test("vitrine home — capture complète", async ({ page }) => {
  await page.goto(`${VITRINE}/fr`);
  await page.waitForLoadState("networkidle");
  await page.screenshot({
    path: `audit-captures/vitrine-home.png`,
    fullPage: true,
  });

  // Vérifier explicitement si la section blog est rendue
  const blogSection = await page.locator("a[href*='/blog/']").count();
  console.log(`[BLOG SECTION] Liens vers /blog/<slug>/ trouvés : ${blogSection}`);

  const eyebrow = await page.getByText(/blog|actualit/i).count();
  console.log(`[BLOG SECTION] Textes 'blog/actualité' : ${eyebrow}`);
});
