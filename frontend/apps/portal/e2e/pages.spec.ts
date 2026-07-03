import { test, expect } from "./fixtures";

/**
 * Vérifie que les pages neuves créées par LOT P-A chargent correctement
 * une fois le membre authentifié. On ne fait pas de POST réel (on évite
 * de pourrir la DB de tests), juste le rendu + les éléments clés.
 */

test.describe("Pages portail LOT P-A", () => {
  test("/fr/carnet — section commandes + documents", async ({ authedPage }) => {
    await authedPage.goto("/fr/carnet");

    await expect(
      authedPage.getByRole("heading", { name: /Mon carnet de collecte/i }),
    ).toBeVisible();

    // CTA principal
    await expect(
      authedPage.getByRole("button", { name: /Commander un carnet/i }),
    ).toBeVisible();

    // Section documents (règlement + spécimen)
    await expect(authedPage.getByText(/Règlement intérieur/i)).toBeVisible();
    await expect(authedPage.getByText(/Spécimen du carnet/i)).toBeVisible();
  });

  test("/fr/profil — formulaire infos + mot de passe", async ({ authedPage }) => {
    await authedPage.goto("/fr/profil");

    await expect(
      authedPage.getByRole("heading", { name: /Mes informations/i }),
    ).toBeVisible();

    // Formulaire coordonnées
    await expect(authedPage.getByLabel(/Prénom/i)).toBeVisible();
    await expect(authedPage.getByLabel(/Nom/i)).toBeVisible();
    await expect(authedPage.getByLabel(/Téléphone/i)).toBeVisible();

    // Formulaire mot de passe
    await expect(authedPage.getByRole("heading", { name: /Mot de passe/i })).toBeVisible();
    await expect(
      authedPage.getByRole("button", { name: /Changer le mot de passe/i }),
    ).toBeVisible();
  });

  test("/fr/credit/remboursement — liste ou état vide", async ({ authedPage }) => {
    await authedPage.goto("/fr/credit/remboursement");

    await expect(
      authedPage.getByRole("heading", { name: /Régler une échéance/i }),
    ).toBeVisible();

    // Soit liste de crédits, soit message "Aucun crédit actif"
    const hasList = await authedPage
      .getByRole("button", { name: /Rembourser/i })
      .first()
      .isVisible()
      .catch(() => false);
    const hasEmpty = await authedPage
      .getByText(/Aucun crédit actif/i)
      .isVisible()
      .catch(() => false);
    expect(hasList || hasEmpty).toBeTruthy();
  });

  test("/fr/credit/reconduction — formulaire si crédit actif", async ({
    authedPage,
  }) => {
    await authedPage.goto("/fr/credit/reconduction");

    await expect(
      authedPage.getByRole("heading", { name: /Demander une reconduction/i }),
    ).toBeVisible();

    // Soit on a le form (modalité comptant/reporté), soit état vide
    const hasModalite = await authedPage
      .getByText(/Comptant.*10/i)
      .first()
      .isVisible()
      .catch(() => false);
    const hasEmpty = await authedPage
      .getByText(/Aucun crédit/i)
      .isVisible()
      .catch(() => false);
    expect(hasModalite || hasEmpty).toBeTruthy();
  });

  test("/fr/epargne/classique — redirige vers /epargne/depot", async ({
    authedPage,
  }) => {
    await authedPage.goto("/fr/epargne/classique");

    // Attend la redirection vers /epargne/depot?context=epargne-classique
    await authedPage.waitForURL(
      (url) => url.pathname.includes("/epargne/depot"),
      { timeout: 5_000 },
    );
    expect(authedPage.url()).toContain("context=epargne-classique");
  });
});

test.describe("Pages portail LOT P-B (compléments)", () => {
  test("/fr/epargne/depot — sélecteur multi-jours visible (context=savings)", async ({
    authedPage,
  }) => {
    await authedPage.goto("/fr/epargne/depot?context=savings");

    // Le bloc multi-jours est rendu pour la cotisation journalière
    await expect(authedPage.getByText(/Couvrir combien de jours/i)).toBeVisible();
    await expect(authedPage.getByLabel(/Jours/i)).toBeVisible();
  });

  test("/fr/epargne/depot — passage multi-jours met à jour le total", async ({
    authedPage,
  }) => {
    await authedPage.goto("/fr/epargne/depot?context=savings");
    const nbJours = authedPage.getByLabel(/Jours/i);
    await nbJours.fill("3");
    // Total affiché : 3 × 1000 = 3 000 XAF
    await expect(authedPage.getByText(/Total.*3.?000.*XAF/i)).toBeVisible();
  });
});
