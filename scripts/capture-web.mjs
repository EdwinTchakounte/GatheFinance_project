#!/usr/bin/env node
/**
 * Capture automatisée des pages web (vitrine + portail + admin).
 *
 * Pré-requis :
 *   npm i -D playwright @playwright/test
 *   npx playwright install chromium
 *
 * Lancement (depuis la racine du dépôt) :
 *   node scripts/capture-web.mjs
 *
 * Sortie : docs/captures/web/{vitrine|portail|admin}/{slug}.png
 *
 * Toutes les URL sont configurables via env vars :
 *   VITRINE_URL   (default http://localhost:3200)
 *   PORTAL_URL    (default http://localhost:3201)
 *   ADMIN_URL     (default http://localhost:3202)
 *
 * Les comptes de test viennent du seed `seed_test_accounts.py`.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

const VITRINE = process.env.VITRINE_URL || "http://localhost:3200";
const PORTAL = process.env.PORTAL_URL || "http://localhost:3201";
const ADMIN = process.env.ADMIN_URL || "http://localhost:3202";

const OUT_DIR = "docs/captures/web";
const VIEWPORT = { width: 1440, height: 900 };

const VITRINE_PAGES = [
  { slug: "01-home", path: "/" },
  { slug: "02-a-propos", path: "/a-propos" },
  { slug: "03-services", path: "/services-financiers" },
  { slug: "04-devenir-membre", path: "/devenir-membre" },
  { slug: "05-blog", path: "/blog" },
  { slug: "06-contact", path: "/contact" },
];

const PORTAL_PAGES = [
  { slug: "01-dashboard", path: "/" },
  { slug: "02-notifications", path: "/notifications" },
  { slug: "03-credit", path: "/credit" },
  { slug: "04-epargne-depot", path: "/epargne/depot" },
  { slug: "05-epargne-retrait", path: "/epargne/retrait" },
];

const ADMIN_PAGES = [
  { slug: "01-dashboard", path: "/dashboard" },
  { slug: "02-membership-requests", path: "/membership-requests" },
  { slug: "03-loan-requests", path: "/loan-requests" },
  { slug: "04-loans", path: "/loans" },
  { slug: "05-payments", path: "/payments" },
  { slug: "06-withdrawals", path: "/withdrawals" },
  { slug: "07-members", path: "/members" },
  { slug: "08-brc", path: "/brc" },
  { slug: "09-renewals", path: "/renewals" },
  { slug: "10-campaigns", path: "/campaigns" },
  { slug: "11-escalations", path: "/escalations" },
  { slug: "12-costs", path: "/costs" },
  { slug: "13-app-settings", path: "/app-settings" },
  { slug: "14-cron-schedules", path: "/cron-schedules" },
  { slug: "15-cooperative-asset", path: "/cooperative-asset" },
  { slug: "16-announcements", path: "/announcements" },
];


async function capture(page, baseUrl, pageDef, outDir) {
  const url = `${baseUrl}${pageDef.path}`;
  console.log(`  → ${url}`);
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
    // Petite pause pour les animations Reveal/Riverpod
    await page.waitForTimeout(800);
    await page.screenshot({
      path: join(outDir, `${pageDef.slug}.png`),
      fullPage: true,
    });
  } catch (err) {
    console.warn(`  ✗ ${url} : ${err.message}`);
  }
}


async function loginPortal(page, email, password) {
  await page.goto(`${PORTAL}/connexion`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"], input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/(\/(fr|en))?\/?$/, { timeout: 15_000 }).catch(() => {});
  await page.waitForLoadState("networkidle");
}


async function loginAdmin(page, email, password) {
  await page.goto(`${ADMIN}/login`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"], input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard/, { timeout: 15_000 }).catch(() => {});
  await page.waitForLoadState("networkidle");
}


async function main() {
  const vitrineDir = join(OUT_DIR, "vitrine");
  const portalDir = join(OUT_DIR, "portail");
  const adminDir = join(OUT_DIR, "admin");
  await mkdir(vitrineDir, { recursive: true });
  await mkdir(portalDir, { recursive: true });
  await mkdir(adminDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: VIEWPORT,
    locale: "fr-FR",
    timezoneId: "Africa/Douala",
  });

  // ===== Vitrine (anonyme) =====
  console.log("\n[1/3] Vitrine (anonyme)");
  {
    const page = await context.newPage();
    for (const def of VITRINE_PAGES) {
      await capture(page, VITRINE, def, vitrineDir);
    }
    await page.close();
  }

  // ===== Portail (Jean Kamga, membre actif) =====
  console.log("\n[2/3] Portail · jean.kamga@test.local");
  {
    const portalCtx = await browser.newContext({
      viewport: VIEWPORT,
      locale: "fr-FR",
      timezoneId: "Africa/Douala",
    });
    const page = await portalCtx.newPage();
    await loginPortal(page, "jean.kamga@test.local", "test1234");
    for (const def of PORTAL_PAGES) {
      await capture(page, PORTAL, def, portalDir);
    }
    await portalCtx.close();
  }

  // ===== Admin (admin@gathe.test, superuser) =====
  console.log("\n[3/3] Admin · admin@gathe.test");
  {
    const adminCtx = await browser.newContext({
      viewport: VIEWPORT,
      locale: "fr-FR",
      timezoneId: "Africa/Douala",
    });
    const page = await adminCtx.newPage();
    await loginAdmin(page, "admin@gathe.test", "test1234");
    for (const def of ADMIN_PAGES) {
      await capture(page, ADMIN, def, adminDir);
    }
    await adminCtx.close();
  }

  await browser.close();
  console.log(`\n✓ Captures sauvegardées dans ${OUT_DIR}/`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
