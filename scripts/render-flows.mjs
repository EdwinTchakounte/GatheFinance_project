#!/usr/bin/env node
/**
 * Rend des diagrammes Mermaid en PNG via Playwright + mermaid.js (CDN).
 *
 * Lancement :
 *   node scripts/render-flows.mjs
 *
 * Les PNG sortent dans docs/flows/ — un fichier par flow déclaré dans FLOWS.
 * Largeur par défaut 1600px (lisible client / présentation).
 */
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

const OUT_DIR = "docs/flows";
const WIDTH = 1600;

const FLOWS = [
  {
    slug: "adhesion-to-actif",
    title: "Adhésion membre — bascule statut → actif après paiement complet des frais",
    mermaid: `flowchart TD
    A["<b>Visiteur</b><br/>remplit le formulaire d'adhésion<br/>(8 champs Art.3 + pièces)"] --> B[Submit]
    B --> C["Création <b>Member</b> statut=<i>pending</i><br/>+ MembershipRequest"]
    C --> D["Email accusé de réception<br/>+ notif file admin"]
    D --> E{"Admin examine dossier<br/>+ entretien Art.3"}
    E -->|"Refusé"| F["statut=<i>refuse</i><br/>+ email motif"]
    E -->|"Validé"| G["statut=<b>approuve_paiement_attendu</b><br/>Génération 3 factures :<br/>• adhésion 10 000<br/>• inscription 2 000<br/>• carnet 1 000"]
    G --> H["Le futur membre voit dans le portail/mobile :<br/>3 frais à régler (Tara ou agence Akwa Bercy)"]
    H --> I{"Paiement"}
    I -->|"Partiel (1 ou 2 sur 3)"| H
    I -->|"<b>Tous les 3 frais payés</b>"| J["Hook <b>on_membership_fees_settled</b><br/>statut=<b>actif</b> + activation_date<br/>+ carnet généré"]
    J --> K["Email bienvenue<br/>+ Règlement Intérieur PDF<br/>+ accès complet à l'app"]
    K --> L([Membre actif])

    classDef start fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef pending fill:#FFF3E0,stroke:#E65100,color:#BF360C
    classDef ok fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    classDef ko fill:#FFEBEE,stroke:#C62828,color:#B71C1C
    classDef final fill:#1B5E20,stroke:#1B5E20,color:#fff

    class A,B start
    class C,G,H pending
    class D,J,K ok
    class F ko
    class L final`,
  },
  {
    slug: "credit-double-approbation",
    title: "Crédit — flow double approbation (temporaire → descente terrain → définitive)",
    mermaid: `flowchart TD
    A["<b>Membre actif</b><br/>remplit formulaire crédit dynamique<br/>+ uploads (CNI, plan loc, CGA?, CFP?)"] --> B["Pré-check éligibilité :<br/>• 20% du montant sur comptes ?<br/>• statut actif ?<br/>• pas de prêt en cours bloquant ?"]
    B -->|"Échec"| X["Rejet automatique<br/>+ raison affichée"]
    B -->|"OK"| C["Affichage <b>frais d'étude</b> = LOAN_STUDY_FEE_AMOUNT"]
    C --> D{"Paiement frais d'étude<br/>(Tara ou agence)"}
    D -->|"Échec / abandon"| C
    D -->|"Payé"| E["LoanRequest statut=<b>etude_en_cours</b><br/>+ apparait en file admin"]
    E --> F{"Comité étudie pièces<br/><b>décision temporaire</b>"}
    F -->|"Refus"| G["statut=<i>refusee_temp</i><br/>+ notif motif<br/>(frais étude NON remboursés)"]
    F -->|"Accord temporaire"| H["statut=<b>approuvee_temp</b><br/>+ planification descente terrain"]
    H --> I["Descente terrain<br/>par comité de crédit<br/>(rapport + photos + signatures)"]
    I --> J{"<b>Décision définitive</b>"}
    J -->|"Refus"| G2["statut=<i>refusee_def</i><br/>+ notif motif"]
    J -->|"Accord"| K["statut=<b>approuvee_def</b><br/>+ délai mise à dispo = MAD_DELAY_DAYS"]
    K --> L["Membre indique moyen<br/>de réception (MOMO / présentiel / virement)"]
    L --> M["Génération <b>Note de demande PDF</b><br/>signée comité, archivée"]
    M --> N["<b>Décaissement</b><br/>Capital - 10% intérêts coupés à la source<br/>+ payout Tara en parallèle"]
    N --> O["Création Loan + échéancier<br/>Remboursement souple<br/>(date butoire = obligatoire)"]
    O -->|"Solde à la date butoire"| P([Prêt soldé])
    O -->|"Impayé à la date butoire"| Q["Pénalité 50% Art.12<br/>+ escalade contentieuse phase A"]

    classDef start fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef step fill:#FFF3E0,stroke:#E65100,color:#BF360C
    classDef ok fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    classDef ko fill:#FFEBEE,stroke:#C62828,color:#B71C1C
    classDef warn fill:#FFFDE7,stroke:#F9A825,color:#E65100
    classDef final fill:#1B5E20,stroke:#1B5E20,color:#fff

    class A start
    class B,C,E,H,I,K,L,M,N step
    class O ok
    class X,G,G2 ko
    class Q warn
    class P final`,
  },
  {
    slug: "epargne-types",
    title: "Épargne — deux produits (collecte journalière vs épargne classique)",
    mermaid: `flowchart TD
    Start(["<b>Membre actif</b> veut épargner"]) --> Choice{"Quel type de produit ?"}

    Choice -->|"Collecte journalière"| C1["Versement quotidien<br/>(Tara MOMO ou agence Akwa Bercy)"]
    C1 --> C2["Solde collecte ⬆"]
    C2 --> C3{"Fin de mois ?"}
    C3 -->|"Non"| C1
    C3 -->|"Oui (cron mensuel)"| C4["Coop coupe <b>1%</b> de commission<br/>(AppSetting tunable, jamais 0)"]
    C4 --> C5(["Membre retire le solde net<br/>via Tara ou agence"])

    Choice -->|"Épargne classique"| E1["Versement ponctuel"]
    E1 --> E2{"<b>Mettre en placement</b> ?<br/>(question au dépôt)"}
    E2 -->|"Non — épargne libre"| L1["Compte <b>classique_libre</b> ⬆"]
    L1 --> L2(["Retrait à tout moment<br/>via Tara ou agence"])

    E2 -->|"Oui — placement"| P1["Compte <b>classique_placement</b> ⬆<br/>(BLOQUÉ jusqu'à anniversaire)"]
    P1 --> P2["Cron mensuel : intérêt <b>1%/mois</b><br/>capitalisé sur solde placé"]
    P2 --> P3{"1 an écoulé ?"}
    P3 -->|"Non"| P2
    P3 -->|"Oui"| P4["<b>Anniversaire</b> : déblocage<br/>+ choix renouveler ou retirer"]
    P4 --> P5(["Retrait possible<br/>via Tara ou agence"])

    classDef start fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef collecte fill:#E1F5FE,stroke:#0277BD,color:#01579B
    classDef libre fill:#FFF8E1,stroke:#F9A825,color:#E65100
    classDef placement fill:#F3E5F5,stroke:#7B1FA2,color:#4A148C
    classDef final fill:#1B5E20,stroke:#1B5E20,color:#fff

    class Start,Choice start
    class C1,C2,C3,C4 collecte
    class E1,E2,L1 libre
    class P1,P2,P3,P4 placement
    class C5,L2,P5 final`,
  },
];

function htmlTemplate(mermaidSource, title) {
  return `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>${title}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
<style>
  body {
    margin: 0;
    padding: 48px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #ffffff;
    color: #0F172A;
  }
  h1 {
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #0B3D2E;
  }
  .subtitle {
    font-size: 13px;
    color: #64748B;
    margin: 0 0 32px 0;
    border-bottom: 1px solid #E2E8F0;
    padding-bottom: 16px;
  }
  #diagram {
    background: #fff;
  }
  .footer {
    margin-top: 32px;
    font-size: 11px;
    color: #94A3B8;
  }
</style>
</head>
<body>
  <h1>${title}</h1>
  <div class="subtitle">GATHE Finance — Référentiel métier 2026</div>
  <div id="diagram" class="mermaid">${mermaidSource}</div>
  <div class="footer">Généré automatiquement (scripts/render-flows.mjs)</div>
<script>
  mermaid.initialize({
    startOnLoad: true,
    theme: "default",
    securityLevel: "loose",
    flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis", padding: 20 },
    themeVariables: {
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
      primaryColor: "#E3F2FD",
      primaryTextColor: "#0D47A1",
      primaryBorderColor: "#1565C0",
      lineColor: "#475569",
      fontSize: "15px"
    }
  });
</script>
</body>
</html>`;
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: 2400 },
    deviceScaleFactor: 2,
  });

  for (const flow of FLOWS) {
    const page = await context.newPage();
    const html = htmlTemplate(flow.mermaid, flow.title);
    // Écrit un fichier temp pour que mermaid puisse charger depuis le CDN
    // sans contraintes file:// — on le sert via setContent + waitForLoadState.
    await page.setContent(html, { waitUntil: "networkidle", timeout: 30_000 });
    // Attente du SVG rendu par mermaid
    await page.waitForSelector("#diagram svg", { timeout: 15_000 });
    await page.waitForTimeout(500); // marge pour fonts

    const out = join(OUT_DIR, `${flow.slug}.png`);
    // Capture la zone utile (body) — pleine page pour ne rien couper
    await page.screenshot({
      path: out,
      fullPage: true,
      type: "png",
    });
    console.log(`✓ ${out}`);
    await page.close();
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
