#!/usr/bin/env node
/**
 * Capture « dossier de présentation » — portail membre sous 3 états de compte,
 * pour illustrer les flows (suspendu → actif → actif avec crédit).
 *
 * Login robuste : on attend explicitement la réponse 200 de /auth/me après
 * le POST /auth/login/ (le waitForURL de l'ancien script matchait /connexion
 * et enchaînait trop tôt).
 *
 * Sortie : docs/captures/live/portail-<etat>/<slug>.png
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";

const PORTAL = process.env.PORTAL_URL || "http://localhost:3201";
const OUT = "docs/captures/live";
const VIEWPORT = { width: 1440, height: 900 };

const PORTAL_PAGES = [
  { slug: "01-accueil", path: "/" },
  { slug: "02-credit", path: "/credit" },
  { slug: "03-epargne-depot", path: "/epargne/depot" },
  { slug: "04-epargne-retrait", path: "/epargne/retrait" },
  { slug: "05-notifications", path: "/notifications" },
];

const ACCOUNTS = [
  { etat: "suspendu", email: "paul.suspendu@test.local", pass: "test1234" },
  { etat: "actif", email: "jean.kamga@test.local", pass: "test1234" },
  { etat: "actif-credit", email: "marie.tankam@test.local", pass: "test1234" },
];

async function loginPortal(page, email, password) {
  await page.goto(`${PORTAL}/connexion`, { waitUntil: "networkidle" });
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"], input[name="password"]', password);
  // On déclenche le submit ET on attend la confirmation d'auth (/auth/me 200).
  const meOk = page.waitForResponse(
    (r) => /\/auth\/me\/?$/.test(r.url()) && r.status() === 200,
    { timeout: 15_000 },
  ).catch(() => null);
  await page.click('button[type="submit"]');
  await meOk;
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(600);
}

async function capture(page, pageDef, outDir) {
  const url = `${PORTAL}${pageDef.path}`;
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(900);
    await page.screenshot({ path: join(outDir, `${pageDef.slug}.png`), fullPage: true });
    console.log(`  ✓ ${pageDef.slug}  (${url})`);
  } catch (err) {
    console.warn(`  ✗ ${pageDef.slug} : ${err.message}`);
  }
}

async function main() {
  const browser = await chromium.launch();
  for (const acc of ACCOUNTS) {
    const dir = join(OUT, `portail-${acc.etat}`);
    await mkdir(dir, { recursive: true });
    console.log(`\n[${acc.etat}] ${acc.email}`);
    const ctx = await browser.newContext({ viewport: VIEWPORT, locale: "fr-FR", timezoneId: "Africa/Douala" });
    const page = await ctx.newPage();
    await loginPortal(page, acc.email, acc.pass);
    console.log(`  → connecté, URL=${page.url()}`);
    for (const def of PORTAL_PAGES) await capture(page, def, dir);
    await ctx.close();
  }
  await browser.close();
  console.log(`\n✓ Terminé → ${OUT}/`);
}

main().catch((e) => { console.error(e); process.exit(1); });
