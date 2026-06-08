#!/usr/bin/env node
/**
 * Captures complémentaires (modales, formulaires, fiches détail) côté admin.
 * Lancement depuis la racine du dépôt après que le script principal
 * capture-web.mjs a déjà loggé l'admin.
 *
 *   node scripts/capture-extras.mjs
 *
 * Les nouvelles captures sont déposées dans docs/captures/web/admin/
 * avec des préfixes en 1X (17-, 18-, 19-, etc.).
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

const ADMIN = process.env.ADMIN_URL || "http://localhost:3202";
const OUT_DIR = "docs/captures/web/admin";
const VIEWPORT = { width: 1440, height: 900 };

async function loginAdmin(page) {
  await page.goto(`${ADMIN}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"], input[name="email"]', "admin@gathe.test");
  await page.fill('input[type="password"], input[name="password"]', "test1234");
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 }).catch(() => {});
  await page.waitForLoadState("networkidle");
}

async function captureModal(page, route, openButtonText, slug) {
  const url = `${ADMIN}${route}`;
  console.log(`  → ${url} → click "${openButtonText}" → ${slug}`);
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(800);
    // Click sur le bouton qui ouvre la modale (par texte)
    await page.getByRole("button", { name: openButtonText }).first().click({ timeout: 5_000 });
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: join(OUT_DIR, `${slug}.png`),
      fullPage: false, // on garde la viewport pour voir la modale en place
    });
  } catch (err) {
    console.warn(`  ✗ ${slug} : ${err.message}`);
  }
}

async function captureDetailFirstRow(page, route, slug) {
  const url = `${ADMIN}${route}`;
  console.log(`  → ${url} → first row → ${slug}`);
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(800);
    // Tente de cliquer sur la 1re ligne de la table principale
    const firstRow = await page.locator("table tbody tr").first();
    await firstRow.click({ timeout: 5_000 });
    await page.waitForTimeout(1200);
    await page.screenshot({
      path: join(OUT_DIR, `${slug}.png`),
      fullPage: false,
    });
  } catch (err) {
    console.warn(`  ✗ ${slug} : ${err.message}`);
  }
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    locale: "fr-FR",
    timezoneId: "Africa/Douala",
  });
  const page = await context.newPage();

  console.log("Login admin@gathe.test...");
  await loginAdmin(page);

  console.log("\n[Modales création]");
  // Bouton "+ Nouvelle annonce" (peut être nommé "Créer une annonce" ou "Nouvelle annonce")
  await captureModal(page, "/announcements", /Nouvelle|Créer|Diffuser|Annonce/i, "17-announcement-form");
  // Bouton "+ Nouvelle campagne"
  await captureModal(page, "/campaigns", /Nouvelle|Créer|Campagne/i, "18-campaign-form");

  console.log("\n[Fiches détail]");
  // Détail crédit (échéancier)
  await captureDetailFirstRow(page, "/loans", "19-loan-detail");
  // Détail membre
  await captureDetailFirstRow(page, "/members", "20-member-detail");
  // Détail demande adhésion
  await captureDetailFirstRow(page, "/membership-requests", "21-membership-detail");
  // Détail demande crédit
  await captureDetailFirstRow(page, "/loan-requests", "22-loan-request-detail");

  await browser.close();
  console.log("\n✓ Captures extras dans " + OUT_DIR);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
