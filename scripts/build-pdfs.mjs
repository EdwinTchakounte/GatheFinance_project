#!/usr/bin/env node
/**
 * Génère 2 PDFs éditoriaux (mobile + admin web) depuis les guides markdown.
 * Style inspiré du Guide EnMKit : couverture brandée + sections numérotées
 * 2 colonnes (capture mobile + callout vert) + filigrane logo discret.
 *
 * Pipeline : markdown → HTML stylé → PDF via Playwright (Chromium).
 */
import { chromium } from "playwright";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { marked } from "marked";

const ROOT = resolve(import.meta.dirname, "..");

const TARGETS = [
  {
    src: "docs/GUIDE_MOBILE.md",
    out: "docs/Guide-Gathe-Finance-Mobile.pdf",
    title: "L'application mobile",
    subtitle: "Gérer son épargne, ses crédits et son carnet — depuis son téléphone.",
    eyebrow: "GUIDE D'UTILISATION",
    appName: "Gathe Finance",
    appVersion: "1.0.0",
    author: "TCHAMBA TCHAKOUNTE Edwin",
    landscape: false,
    flavor: "mobile",
  },
  {
    src: "docs/GUIDE_WEB.md",
    out: "docs/Guide-Gathe-Finance-Web.pdf",
    title: "Le dashboard administrateur",
    subtitle: "L'outil de gestion quotidien de la coopérative.",
    eyebrow: "MANUEL D'ADMINISTRATION",
    appName: "Gathe Finance",
    appVersion: "1.0.0",
    author: "TCHAMBA TCHAKOUNTE Edwin",
    landscape: true,
    flavor: "web",
  },
  {
    src: "docs/GUIDE_RECETTE.md",
    out: "docs/Guide-Gathe-Finance-Recette.pdf",
    title: "Mise en production et recette",
    subtitle: "État réel de la prod, workflows complets et plan de recette utilisateur.",
    eyebrow: "MANUEL DE RECETTE",
    appName: "Gathe Finance",
    appVersion: "1.0.0",
    author: "TCHAMBA TCHAKOUNTE Edwin",
    landscape: false,
    flavor: "web",
  },
  {
    src: "docs/GUIDE_RECETTE_LIVE.md",
    out: "docs/Guide-Gathe-Finance-Recette-Live.pdf",
    title: "Rapport de recette en production",
    subtitle: "Tests bout-en-bout exécutés sur la prod réelle, données conservées pour la présentation.",
    eyebrow: "RAPPORT DE RECETTE",
    appName: "Gathe Finance",
    appVersion: "1.0.0",
    author: "TCHAMBA TCHAKOUNTE Edwin",
    landscape: false,
    flavor: "web",
  },
];

const CSS = `
@page {
  margin: 18mm 16mm 16mm 16mm;
  @bottom-left {
    content: "Gathe Finance · Guide d'utilisation";
    font-family: "DM Sans", sans-serif;
    font-size: 8pt;
    color: #94a3b8;
  }
  @bottom-right {
    content: counter(page);
    font-family: "Syne", serif;
    font-size: 9pt;
    color: #475569;
    font-weight: 600;
  }
}
@page :first {
  margin: 0;
  @bottom-left { content: ""; }
  @bottom-right { content: ""; }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }

body {
  font-family: "DM Sans", "Helvetica Neue", Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.6;
  color: #1f2937;
  background: #ffffff;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

/* ============================================================
   COUVERTURE — style EnMKit, claire, logo en grand
   ============================================================ */
.cover {
  page-break-after: always;
  position: relative;
  width: var(--page-w, 210mm);
  height: var(--page-h, 297mm);
  background:
    radial-gradient(80% 60% at 50% 10%, rgba(58,170,53,0.06), transparent 70%),
    radial-gradient(60% 50% at 50% 100%, rgba(14,77,146,0.05), transparent 70%),
    #fbfdfb;
  overflow: hidden;
}
.cover-inner {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 35mm 25mm 28mm 25mm;
  text-align: center;
}
.cover-top { width: 100%; }
.cover-logo {
  display: block;
  height: 24mm;
  width: auto;
  margin: 0 auto 8mm auto;
}
.cover-accent-bar {
  width: 56px;
  height: 3px;
  background: linear-gradient(90deg, #0E4D92 0%, #3AAA35 100%);
  margin: 0 auto 8mm auto;
  border-radius: 2px;
}
.cover-eyebrow {
  font-size: 10pt;
  letter-spacing: 0.28em;
  color: #0E4D92;
  font-weight: 600;
  margin-bottom: 6mm;
  text-transform: uppercase;
}
.cover h1.title,
.cover .title {
  font-family: "Syne", serif !important;
  font-size: 36pt !important;
  font-weight: 700 !important;
  line-height: 1.05 !important;
  color: #0f1a2e !important;
  margin: 0 auto 6mm auto !important;
  max-width: 145mm;
  border: none !important;
  padding: 0 !important;
  letter-spacing: -0.01em;
  page-break-before: avoid !important;
}
.cover h1.title::before { display: none; }
.cover .subtitle {
  font-size: 12pt;
  color: #475569;
  line-height: 1.55;
  max-width: 130mm;
  margin: 0 auto;
}

.cover-bottom { width: 100%; }
.cover-version-chip {
  display: inline-flex;
  gap: 0.8em;
  align-items: center;
  background: #eaf2fc;
  border: 1px solid rgba(14,77,146,0.18);
  padding: 0.45em 1.1em;
  border-radius: 999px;
  font-size: 9pt;
  color: #475569;
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 10mm;
}
.cover-version-chip strong { color: #0E4D92; font-weight: 700; }
.cover-version-chip .dot { color: #cbd5e1; }

.cover-signed {
  font-size: 8.5pt;
  letter-spacing: 0.22em;
  color: #94a3b8;
  text-transform: uppercase;
  margin-bottom: 5mm;
}
.cover-author {
  font-family: "Syne", serif;
  font-size: 14pt;
  font-weight: 600;
  color: #0E4D92;
  letter-spacing: 0.01em;
}

/* ============================================================
   FILIGRANE — logo discret en arrière-plan
   ============================================================ */
main { position: relative; }
.watermark {
  position: fixed;
  top: 50%;
  left: 50%;
  width: 130mm;
  transform: translate(-50%, -50%) rotate(-12deg);
  opacity: 0.05;
  z-index: -1;
  pointer-events: none;
}

/* ============================================================
   TITRES & BLOCS DE PAGE
   ============================================================ */
h1, h2, h3, h4 {
  font-family: "Syne", serif;
  font-weight: 600;
  color: #0E4D92;
  line-height: 1.22;
}
h1 {
  font-size: 22pt;
  margin: 0 0 0.4em 0;
  page-break-before: always;
  page-break-after: avoid;
}
h1::before {
  content: "";
  display: block;
  width: 48px;
  height: 3px;
  background: linear-gradient(90deg, #0E4D92, #3AAA35);
  border-radius: 2px;
  margin-bottom: 0.4em;
}
h1:first-of-type { page-break-before: auto; }
h2 { font-size: 14pt; margin: 1.4em 0 0.5em 0; page-break-after: avoid; }
h3 { font-size: 11.5pt; margin: 1em 0 0.3em 0; color: #1a5dab; page-break-after: avoid; }
h4 { font-size: 10.5pt; margin: 0.8em 0 0.25em 0; color: #C2742A; }

p { margin: 0.4em 0 0.7em 0; }
ul, ol { margin: 0.3em 0 0.7em 1.3em; }
li { margin: 0.22em 0; }
li::marker { color: #3AAA35; }
a { color: #0E4D92; text-decoration: none; }
strong { color: #0E4D92; font-weight: 600; }
hr { border: 0; border-top: 1px solid #e5e7eb; margin: 1.5em 0; }

/* ============================================================
   SOMMAIRE (en encadré clair, 2 colonnes)
   ============================================================ */
.toc {
  margin: 0 0 1.5em 0;
  padding: 1.4em 1.6em 1.2em 1.6em;
  background: linear-gradient(180deg, #f7faff 0%, #eef4fc 100%);
  border-radius: 12px;
  border: 1px solid #dde6f2;
  page-break-inside: avoid;
}
.toc h2 {
  margin: 0 0 0.8em 0 !important;
  font-size: 12pt;
  color: #0E4D92;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.toc ol {
  list-style: none;
  counter-reset: tocnum;
  padding: 0; margin: 0;
  font-size: 10.5pt;
  columns: 2;
  column-gap: 2em;
}
.toc ol li {
  counter-increment: tocnum;
  padding: 0.38em 0;
  border-bottom: 1px dotted #cad4e1;
  break-inside: avoid;
  display: flex; gap: 0.6em; align-items: baseline;
}
.toc ol li::marker { content: ""; }
.toc ol li::before {
  content: counter(tocnum) ".";
  font-family: "Syne", serif;
  font-weight: 600;
  color: #3AAA35;
  min-width: 1.6em;
}

/* ============================================================
   SECTION 2 COLONNES — capture + callout (style EnMKit)
   Usage en HTML brut dans le markdown :
   <section class="step">
     <div class="step-head"><span class="step-num">1</span><span class="step-title">…</span></div>
     <div class="step-body">
       <img src="…" />
       <div class="step-card">
         <div class="step-card-head"><span class="step-badge">★</span>Titre</div>
         <ul><li>…</li></ul>
       </div>
     </div>
   </section>
   ============================================================ */
.step {
  margin: 0 0 8mm 0;
  page-break-inside: avoid;
}
.step-head {
  display: flex;
  align-items: center;
  gap: 0.7em;
  margin-bottom: 4mm;
}
.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: linear-gradient(180deg, #0E4D92 0%, #143f70 100%);
  color: #ffffff;
  font-family: "Syne", serif;
  font-weight: 700;
  font-size: 12pt;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(14,77,146,0.20);
}
.step-title {
  font-family: "Syne", serif;
  font-weight: 600;
  color: #0E4D92;
  font-size: 14pt;
  line-height: 1.2;
}
.step-body {
  display: grid;
  grid-template-columns: 56mm 1fr;
  gap: 6mm;
  align-items: start;
}
.step-body img {
  display: block;
  width: 100%;
  max-height: 110mm;
  height: auto;
  object-fit: contain;
  border-radius: 12px;
  border: 1px solid #e6ebf2;
  box-shadow: 0 4px 14px rgba(14,77,146,0.10);
  margin: 0;
}
.step-card {
  background: linear-gradient(180deg, #f5fbf4 0%, #eff8ee 100%);
  border-left: 3px solid #3AAA35;
  border-radius: 0 12px 12px 0;
  padding: 1em 1.2em 1em 1.2em;
  font-size: 9.8pt;
  line-height: 1.55;
  color: #1f2937;
  box-shadow: 0 1px 3px rgba(58,170,53,0.08);
}
.step-card-head {
  display: flex;
  align-items: center;
  gap: 0.55em;
  margin-bottom: 0.55em;
  font-family: "Syne", serif;
  font-weight: 600;
  font-size: 11pt;
  color: #2e8a4f;
}
.step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: linear-gradient(180deg, #3AAA35 0%, #2e8a4f 100%);
  color: #ffffff;
  font-size: 11pt;
  font-weight: 700;
  flex-shrink: 0;
}
.step-card ul { margin: 0.3em 0 0.4em 1.2em; }
.step-card li { margin: 0.25em 0; }
.step-card p { margin: 0.3em 0; }
.step-card strong { color: #2e8a4f; }

/* Variante double : 2 captures côte à côte si nécessaire */
.step-body.dual-shots {
  grid-template-columns: 35mm 35mm 1fr;
}
.step-body.dual-shots img { max-height: 100mm; }

/* Variante full-width : pas de capture, juste un encadré pleine largeur */
.step-body.full-card {
  grid-template-columns: 1fr;
}

/* ============================================================
   CALLOUT (encadré bleu d'info, comme la "principe d'EnMKit")
   ============================================================ */
blockquote, .info-box {
  background: linear-gradient(180deg, #eef5fc 0%, #e2eefa 100%);
  border-left: 3px solid #0E4D92;
  border-radius: 0 10px 10px 0;
  padding: 0.9em 1.1em;
  margin: 1em 0;
  font-size: 9.8pt;
  color: #1c2733;
  page-break-inside: avoid;
}
blockquote strong { color: #0E4D92; }
blockquote p { margin: 0.2em 0; }

/* ============================================================
   MARQUES D'UI
   ============================================================ */
.ui-btn {
  display: inline-block;
  background: linear-gradient(180deg, #2e8a4f 0%, #246a3d 100%);
  color: #ffffff;
  font-weight: 600;
  font-size: 9.4pt;
  padding: 2px 10px 3px 10px;
  border-radius: 999px;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(36,106,61,0.25);
  vertical-align: 1px;
}
.ui-btn-outline {
  display: inline-block;
  background: #ffffff;
  color: #2e8a4f;
  font-weight: 600;
  font-size: 9.4pt;
  padding: 1.5px 9px 2.5px 9px;
  border-radius: 999px;
  border: 1.5px solid #2e8a4f;
  white-space: nowrap;
  vertical-align: 1px;
}
.ui-tab {
  display: inline-block;
  background: #eaf2fc;
  color: #0E4D92;
  font-weight: 600;
  font-size: 9.4pt;
  padding: 1.5px 9px 2.5px 9px;
  border-radius: 6px;
  border: 1px solid rgba(14,77,146,0.18);
  white-space: nowrap;
  vertical-align: 1px;
}
.ui-chip {
  display: inline-block;
  background: #fdf4e7;
  color: #B85C0F;
  font-weight: 600;
  font-size: 9.2pt;
  padding: 1px 8px 1.5px 8px;
  border-radius: 999px;
  border: 1px solid rgba(184,92,15,0.20);
  white-space: nowrap;
  vertical-align: 1px;
}
code {
  font-family: "DM Sans", sans-serif;
  font-size: 9.5pt;
  font-weight: 600;
  background: #eef2f7;
  color: #0E4D92;
  padding: 1px 6px;
  border-radius: 4px;
}

/* ============================================================
   TABLEAUX
   ============================================================ */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.8em 0 1em 0;
  font-size: 9.8pt;
  page-break-inside: avoid;
  background: #ffffff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(14,77,146,0.06);
}
th {
  background: linear-gradient(180deg, #0E4D92 0%, #143f70 100%);
  color: #ffffff;
  padding: 0.5em 0.8em;
  text-align: left;
  font-family: "Syne", serif;
  font-weight: 600;
  font-size: 9.4pt;
  letter-spacing: 0.04em;
}
td { padding: 0.5em 0.8em; border-bottom: 1px solid #eef2f7; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
tr:nth-child(even) td { background: #f9fbfd; }

/* ============================================================
   IMAGES classiques (en dehors des sections .step)
   ============================================================ */
img {
  max-width: 100%;
  height: auto;
  border-radius: 12px;
  border: 1px solid #e6ebf2;
  box-shadow: 0 4px 14px rgba(14,77,146,0.10);
  page-break-inside: avoid;
}
.flavor-mobile main > p > img { max-width: 60%; display: block; margin: 1em auto; }
.flavor-web main > p > img {
  max-width: 92%; display: block; margin: 0.4em auto 0.8em auto;
  max-height: 130mm; page-break-inside: avoid;
}
.flavor-web h1 { font-size: 17pt; }
.flavor-web h1::before { width: 36px; height: 2px; margin-bottom: 0.3em; }
.flavor-web h2 { font-size: 12pt; margin: 0.9em 0 0.4em 0; }
.flavor-web body { font-size: 10pt; }
`;

/* --------------------------------------------------------------- */

const COVER_HTML = (t) => `
<section class="cover">
  <div class="cover-inner">
    <div class="cover-top">
      <img class="cover-logo" src="assets/logo.png" alt="Gathe Finance" />
      <div class="cover-accent-bar"></div>
      <div class="cover-eyebrow">${t.eyebrow}</div>
      <h1 class="title">${t.title}</h1>
      <p class="subtitle">${t.subtitle}</p>
    </div>
    <div class="cover-bottom">
      <div class="cover-version-chip">
        Application <strong>${t.appName}</strong>
        <span class="dot">·</span> Version <strong>${t.appVersion}</strong>
        <span class="dot">·</span> ${t.dateStr}
      </div>
      <div class="cover-signed">Document préparé par</div>
      <div class="cover-author">${t.author}</div>
    </div>
  </div>
</section>
`;

function injectUiMarks(html) {
  return html
    .replace(/:btnOutline\[([^\]]+)\]/g, (_, x) => `<span class="ui-btn-outline">${x}</span>`)
    .replace(/:btn\[([^\]]+)\]/g, (_, x) => `<span class="ui-btn">${x}</span>`)
    .replace(/:tab\[([^\]]+)\]/g, (_, x) => `<span class="ui-tab">${x}</span>`)
    .replace(/:chip\[([^\]]+)\]/g, (_, x) => `<span class="ui-chip">${x}</span>`);
}

async function buildPdf(t) {
  const md = await readFile(resolve(ROOT, t.src), "utf8");
  const rendered = marked.parse(md, { gfm: true, breaks: false });
  const body = injectUiMarks(rendered);

  const dateStr = new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit", month: "2-digit", year: "numeric",
  }).format(new Date());

  const pageSize = t.landscape ? "A4 landscape" : "A4 portrait";
  const pageW = t.landscape ? "297mm" : "210mm";
  const pageH = t.landscape ? "210mm" : "297mm";
  const pageRule = `@page { size: ${pageSize}; } :root { --page-w: ${pageW}; --page-h: ${pageH}; }`;

  const html = `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <title>${t.eyebrow} — ${t.title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>${pageRule}\n${CSS}</style>
</head>
<body class="flavor-${t.flavor}">
  ${COVER_HTML({ ...t, dateStr })}
  <main>
    <img class="watermark" src="assets/logo.png" alt="" />
    ${body}
  </main>
</body>
</html>`;

  const htmlPath = resolve(ROOT, "docs/" + (t.flavor === "mobile" ? "Guide-Gathe-Finance-Mobile" : "Guide-Gathe-Finance-Web") + ".html");
  await writeFile(htmlPath, html, "utf8");

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`file://${htmlPath}`, { waitUntil: "load", timeout: 90000 });
  // Petit délai pour que les @font-face Google se chargent si la prod a un accès web,
  // mais on n'attend plus le networkidle complet (qui timeoute hors-ligne).
  await page.waitForTimeout(2500);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(900);

  const outPath = resolve(ROOT, t.out);
  await page.pdf({
    path: outPath,
    format: "A4",
    landscape: !!t.landscape,
    printBackground: true,
    margin: { top: 0, bottom: 0, left: 0, right: 0 },
    displayHeaderFooter: false,
    preferCSSPageSize: true,
  });
  await browser.close();
  console.log(`  ✓ ${t.out}`);
}

async function main() {
  console.log("Construction des PDFs Gathe Finance...\n");
  for (const t of TARGETS) {
    console.log(`▶ ${t.src} → ${t.out}`);
    await buildPdf(t);
  }
  console.log("\n✓ PDFs générés dans docs/");
}

main().catch((err) => { console.error(err); process.exit(1); });
