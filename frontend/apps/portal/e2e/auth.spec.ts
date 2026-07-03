import { test, expect } from "@playwright/test";

import { PORTAL_EMAIL, PORTAL_PASSWORD } from "./fixtures";

test.describe("Authentification portail", () => {
  test("affiche la page de connexion en split-screen", async ({ page }) => {
    await page.goto("/fr/connexion");

    // Split-screen : visuel à gauche en desktop, formulaire à droite
    await expect(page.getByRole("heading", { name: /Bon retour parmi nous/i })).toBeVisible();
    await expect(page.getByLabel(/Adresse e-mail/i)).toBeVisible();
    await expect(page.getByLabel(/^Mot de passe$/i)).toBeVisible();

    // Lien adhésion + mot de passe oublié
    await expect(page.getByRole("link", { name: /Faire une demande d'adhésion/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Oublié/i })).toBeVisible();
  });

  test("refuse des identifiants invalides", async ({ page }) => {
    await page.goto("/fr/connexion");
    await page.getByLabel(/Adresse e-mail/i).fill("inconnu@example.com");
    await page.getByLabel(/^Mot de passe$/i).fill("badpassword");
    await page.getByRole("button", { name: /Se connecter/i }).click();

    // Erreur visible (401 -> "Identifiants invalides"). 2 elements ont
    // role=alert sur la page (Next.js banner + notre <p role=alert>), on
    // cible le premier qui est le message d'erreur du form.
    await expect(page.getByRole("alert").first()).toContainText(/Identifiants/i, {
      timeout: 10_000,
    });
  });

  test("login OK redirige vers le tableau de bord", async ({ page }) => {
    await page.goto("/fr/connexion");
    await page.getByLabel(/Adresse e-mail/i).fill(PORTAL_EMAIL);
    await page.getByLabel(/^Mot de passe$/i).fill(PORTAL_PASSWORD);
    await page.getByRole("button", { name: /Se connecter/i }).click();

    // Redirection vers /fr (dashboard) sous 15s
    await page.waitForURL((url) => !url.pathname.includes("/connexion"), {
      timeout: 15_000,
    });

    // Le dashboard charge — un élément discriminant doit être visible
    // (soit le solde, soit le menu de nav, soit le bouton "Se déconnecter")
    const hasNav = await page
      .getByRole("navigation")
      .first()
      .isVisible()
      .catch(() => false);
    const hasSolde = await page
      .getByText(/épargne|collecte|solde/i)
      .first()
      .isVisible()
      .catch(() => false);
    expect(hasNav || hasSolde).toBeTruthy();
  });
});
