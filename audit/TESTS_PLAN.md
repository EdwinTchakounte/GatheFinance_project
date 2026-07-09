# Plan de tests GATHE Finance

> Auteur : Tchamba Tchakounte Edwin
> Date : 2026-06-20
> Objectif : catalogue exhaustif des tests à maintenir avant publication production. Trois niveaux de priorité (P0, P1, P2). Les blocs P0 conditionnent la mise en ligne.

---

## 1. Pyramide cible

```
                        e2e Playwright (web)   |   integration_test (mobile)
                   |————————————————————————————|————————————————————————————|
                   API tests pytest (DRF)       |   widget tests Flutter
            |———————————————————————————————————|——————————————————————————————|
            UseCases / Services / Models pytest  |  domain layer tests Flutter
   |————————————————————————————————————————————|—————————————————————————————|
```

Cibles de couverture : Backend 75 %, Mobile 60 %, Web 50 % e2e parcours critiques.

---

## 2. Backend Django (pytest, P0)

### 2.1 Tests existants (déjà en place)

* 521 tests pytest passent, 1 fail SQL connu, 1 skip.
* Fichiers répartis dans `backend/tests/` et `apps_coop/*/tests/`.

### 2.2 P0 à ajouter

| Domaine                    | Test à écrire                                                                 |
| -------------------------- | ----------------------------------------------------------------------------- |
| Activation membre (CH-2)   | Quand les 3 frais sont validés, Member.statut bascule à ACTIF automatiquement |
| Reconduction crédit Art.10 | +1 mois fixe, taux 10 % comptant, recalcul échéancier sur capital restant     |
| Reconduction crédit Art.11 | Taux 15 % reporté, idem                                                       |
| Reconduction crédit Art.50 | Taux 50 % sur capital, 1 seule fois                                           |
| Mise en demeure Art.13     | Cron incrémente `mise_en_demeure_count` + génère lettre PDF + envoi email     |
| Microcampaign SQL bug      | Fix puis test passe : `test_valide_passes_to_en_instruction`                  |

### 2.3 P1

| Domaine                | Test                                                                  |
| ---------------------- | --------------------------------------------------------------------- |
| Idempotency Tara       | Webhook reçu 2 fois avec même idempotency_key, état unchangé         |
| HMAC Tara              | Signature invalide, requête refusée 400                              |
| Throttle login         | 21 tentatives en 1h, 21e refusée 429                                  |
| Saisie épargne R1      | Vérifier exclusion tranches prêteur ENGAGEE, inclusion avaliste       |
| Funding 24h            | Au-delà de 24h, status → REALLOCATING + redistribution                |
| Cron commission 1 %    | Bilan mensuel cohérent avec mouvements de la période                  |
| Anniversaire épargne   | À J+365, état contrat → MATURE + restitution + frais ré-inscription   |

### 2.4 P2

* Tests perf : 100 paiements concurrents sur même membre, pas de double imputation.
* Tests régression seed : `seed_app_settings` + `seed_email_templates` + `seed_event_catalog` idempotents.

---

## 3. Mobile Flutter (P0)

### 3.1 Tests existants

* 118 tests passent (unit + widget). Pas d'integration_test.

### 3.2 P0 à ajouter (integration_test/)

| Scénario                  | Étapes                                                                     |
| ------------------------- | -------------------------------------------------------------------------- |
| Onboarding → login        | 4 slides, login OK, redirection home, solde affiché                        |
| PIN setup au premier login| Création + confirmation, déverrouillage à la reprise                       |
| Verser sur épargne        | Sheet, sélection canal, init paiement, retour confirmation                 |
| Verser cotisation N jours | Sheet, choix multi-jours, commission 1 % affichée, paiement                |
| Demande de crédit         | Formulaire dynamique FormSchema, frais d'étude payés, soumission           |
| Reconduction crédit       | Sheet, taux affiché, paiement frais reconduction (si frais positif)        |
| Désigner un avaliste      | Saisie nom + numéro identification, envoi mandat                           |
| Mandat avaliste reçu      | Réponse Q13 (oui/non), consentement non-rétractable                        |
| Espace prêteur            | Consent, tranches choisies, funding 24h affiché                            |
| Retrait épargne           | Demande retrait, canal MoMo ou présentiel, statut en attente               |
| Notifications             | Annonce broadcast affichée, marquage lu                                    |

### 3.3 P0 widget

| Widget                    | Test                                                                       |
| ------------------------- | -------------------------------------------------------------------------- |
| PinPromptSheet            | Affiche 4 dots, lock après 5 essais, déverrouillage biométrique alternative|
| LoanRequestSheet          | Validation date butoir obligatoire (CH-8), erreur si vide                  |
| DepositSheet              | Validation montant min, calcul commission affiché                          |
| AvalisteDesignationSheet  | Recherche par numéro identification + nom, erreur si introuvable           |

### 3.4 P1

* Tests Dio mock : tous les datasources avec 200, 400, 401, 500, timeouts.
* Tests offline : pas d'internet, message d'erreur cohérent, cache visible.
* Test FLAG_SECURE : `flutter drive` avec assert que `adb screencap` retourne noir.

---

## 4. Web (Playwright e2e, P0)

### 4.1 Existant

* H4 a posé un harnais Playwright. À reprendre.

### 4.2 P0 parcours critiques

| Parcours              | Steps                                                                  |
| --------------------- | ---------------------------------------------------------------------- |
| Vitrine SEO           | Sitemap accessible, robots.txt OK, hreflang FR/EN cohérent             |
| Adhésion              | Vitrine → Devenir membre → Formulaire 8 champs → soumission OK         |
| Portail login         | Connexion, redirection dashboard, solde réel affiché                   |
| Portail dépôt         | Sheet, choix placement vs libre, paiement init                         |
| Portail crédit        | Demande, FormSchema, frais d'étude, note PDF téléchargeable            |
| Portail avaliste      | Réception mandat, consent Q13, statut updated                          |
| Portail prêteur       | Consent + tranches + funding 24h en cours                              |
| Admin auth            | Login, throttle 5/15 min observé                                       |
| Admin validation crédit| Approbation provisoire (CH-6) puis définitive, échéancier généré      |
| Admin BRC             | Filter En attente / Validés / Rejetés, validation passe                |
| Admin retrait         | Approbation, payout Tara init, débit atomique solde                    |
| Admin annonce         | Création annonce broadcast, visible portail + mobile                   |

### 4.3 P1

* Régressions visuelles : Playwright + diff pixel sur 12 pages clés. Tolerance 5 %.
* Accessibilité : axe-core sur vitrine, score min 90/100 chaque page.
* Lighthouse CI : LCP < 2.5 s, TBT < 200 ms, CLS < 0.1 sur home et services.

---

## 5. Sécurité (P0 / P1)

| Test                                  | Outil suggéré                | Priorité |
| ------------------------------------- | ---------------------------- | -------- |
| OWASP ZAP baseline scan               | OWASP ZAP CLI                | P0       |
| Headers de sécurité                   | observatory.mozilla.org      | P0       |
| Webhook HMAC fuzzing                  | script Python custom         | P0       |
| Throttle bypass                       | curl boucle                  | P0       |
| Secrets dans le repo                  | gitleaks scan                | P0       |
| Dépendances vulnérables backend       | pip-audit + safety           | P1       |
| Dépendances vulnérables frontend      | npm audit + better-npm-audit | P1       |
| Dépendances vulnérables mobile        | pub outdated + dart_code_metrics | P1   |
| CSRF replay                           | Burp Suite                   | P1       |
| Session fixation                      | Burp Suite                   | P1       |

---

## 6. Performance et charge (P1)

| Cible                                  | Outil      | Critère                                |
| -------------------------------------- | ---------- | -------------------------------------- |
| Backend `/api/v1/auth/login`            | k6         | p95 < 400 ms à 50 req/s pendant 2 min  |
| Backend `/api/v1/savings/me`            | k6         | p95 < 250 ms à 100 req/s               |
| Backend webhook Tara batch              | k6         | 200 req/s pendant 1 min sans erreur    |
| DB writes sous load                    | pgbench    | Aucun deadlock                         |
| Mobile cold start                       | manuel     | < 2.5 s sur device de référence        |
| Vitrine LCP                             | Lighthouse | < 2.5 s desktop, < 4 s 4G              |

---

## 7. Crons et longue durée (P0)

Tests d'intégration sur les 10 schedules. Pour chacun, créer un fixture, faire « run-now » via endpoint admin, vérifier l'état final.

| Cron                          | Fixture                                | Assert                              |
| ----------------------------- | -------------------------------------- | ----------------------------------- |
| collecte.fin_de_mois          | 30 transactions sur 1 membre           | commission 1 % calculée + visible   |
| epargne.anniversary           | Compte classique J+365                 | Statut MATURE + restitution         |
| loans.overdue                 | Crédit avec échéance dépassée J+31     | Pénalité 50 % posée                 |
| funding.window_expiry         | LoanFundingRequest > 24h               | Statut REALLOCATING                 |
| microcampaign.close_expired   | Campagne avec date_fin passée          | Statut CLOTUREE                     |
| judicial.auto_escalate        | Crédit en phase C depuis > seuil       | Phase D ouverte                     |

---

## 8. CI/CD à mettre en place (P1)

Un workflow GitHub Actions (ou GitLab CI selon repo distant). 4 jobs en parallèle puis 1 job d'intégration :

1. `backend-lint` : flake8 + black + mypy
2. `backend-test` : pytest avec couverture, échec si < 70 %
3. `frontend-test` : pnpm lint + pnpm test
4. `mobile-test` : flutter analyze + flutter test
5. `e2e` (manuel ou tag) : Playwright + integration_test mobile

Build artefacts :

* Backend image Docker poussée sur ghcr.
* Mobile AAB signé, gardé en draft Play Console interne.

---

## 9. Cadence et responsabilités

| Niveau   | Cadence                                              | Responsable      |
| -------- | ---------------------------------------------------- | ---------------- |
| Unit P0  | À chaque commit                                      | Auteur du commit |
| Widget P0 | Nightly + à chaque PR mobile                        | Dev mobile       |
| API P0   | À chaque PR backend                                  | Dev backend      |
| e2e P0   | Avant tout merge en main                             | Dev de garde     |
| Sécurité | Chaque sprint + avant release                        | Lead             |
| Perf     | Avant release + après refactor critique              | Lead infra       |
| Cron     | Avant release + chaque ajout / modif de cron         | Lead backend     |

---

## 10. Critères Go / No-Go pour Play Store + production web

Tous P0 doivent être verts. Détail :

* Backend pytest : 0 échec, couverture >= 70 %.
* Mobile flutter test : 0 échec.
* Mobile integration_test : tous les scénarios P0 passent sur device de référence.
* Web Playwright : tous les parcours P0 verts.
* OWASP ZAP baseline : 0 high.
* Gitleaks : aucun secret détecté.
* AAB signé en release avec keystore prod (cf. `audit/PLAY_STORE.md`).
* Lighthouse home vitrine : score perf >= 85, a11y >= 90.
