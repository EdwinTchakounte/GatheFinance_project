# Note de livraison — 2026-07-27

Branche : `feat/credit-hardening-campaigns-cms-emails`
Périmètre livré : **correctifs terrain + modularité (Lot 0) + gouvernance crédit (G1–G6a)**.

---

## 1. Contenu de la livraison (commits)

**Correctifs terrain** — `70e4d84`, `da42d25`
- P1 frais d'adhésion plus re-réclamés à un compte déjà actif
- P3 card crédit clôturé : libellé « Crédit n°X »
- P4 éligibilité basée sur l'apport (voir gouvernance)
- P5 min/max du formulaire = bornes de la campagne
- P6 frais d'étude campagne corrects au dashboard (paiement manuel)
- P7 campagne sans frais : phase frais sautée
- P8 bouton « Supprimer » sur toutes les demandes de crédit (admin)
- P9 collecte fin de mois : destination Mobile Money remontée au dashboard
- P10 photo de profil effective sur mobile (média public)
- P11 nom dédupliqué « nom prénom » partout ; salutations = prénom seul
- P12 XAF affiché en double corrigé (mobile)

**Modularité — Lot 0 (dette NHR payée)** — `084ddd8`→`b1fabb3`
Le cœur ne dépend plus d'aucun nom de champ spécifique-coopérative : un champ se
déclare « preuve/déclaration de privilège » via des attributs JSON du FormSchema
(`is_brc_proof` / `is_privilege_declaration`, lus par `forms/field_flags.py`).
Base « un socle, plusieurs coopératives ».

**Gouvernance crédit — G1→G6a** — `40dc324`→`21f4df6`
- G1 apport personnel gelé **20 %** (éditable `loans.apport.rate`)
- G2 découvert tracé (`Loan.montant_gage` / `montant_decouvert`, migration 0042)
- G3 criticité crédit (faible→critique, `criticality_services`, settings)
- G4 **plancher 30 % obligatoire pour tous** + privilège comité tracé (`Loan.privilege_accorde`, migration 0043)
- G5 endpoint admin exposition au découvert + paliers d'alerte
- G6a carte admin « Exposition au découvert » (dashboard)

---

## 2. ⚠️ Changements de comportement CRÉDIT (à briefer l'équipe)

Ces règles changent l'octroi de crédit — l'équipe crédit doit être informée **dès la mise en prod** :

1. **Plancher 30 % obligatoire pour TOUS.** Un membre (même ancien) doit détenir 30 %
   du montant en épargne classique disponible pour être éligible. En dessous → inéligible.
   La collecte est exclue de ce calcul (garantie 2026). *Un ancien sous-couvert qui pouvait
   emprunter avant ne le peut plus sans avaliste/garantie.*
2. **Apport gelé = 20 %** du montant (au lieu de 10 %), transférable pour solder le crédit.
3. **Intérêt coupé à la source** (défaut) : le membre reçoit 90 % (montant − 10 % d'intérêt) et
   rembourse le net.
4. **Découvert = part prêtée sur confiance** (montant − gagé), tracé et plafonné à 80 %
   structurellement (grâce à l'apport 20 %). Visible via la criticité et la carte d'exposition.

Tous les taux/seuils sont **éditables dans l'admin** (Paramètres) : apport, plancher éligibilité,
criticité, palier d'alerte, mode intérêt.

---

## 3. Checklist de déploiement

1. **Migrations** : `migrate` (nouvelles : loans `0042` découvert, `0043` privilège ; members `0020`
   `date_activation` **avec backfill** — nullables/idempotentes, safe).
2. **⚠️ Critique (Lot 0.5)** : `python manage.py seed_form_schemas --kind loan_request` + vérifier
   `is_active` **avant/avec** le déploiement. Sinon les champs de privilège (ancien apprenant/CGA)
   seraient ignorés (la boucle compat a été retirée).
3. **Réglages gouvernance** : rien à seeder (défauts dans le CATALOG, éditables admin).
4. **Post-deploy standard** : `bootstrap_site` · `seed_blog` · `seed_email_templates --force` ·
   AppSetting `notifications.admin_url` · env `PUBLIC_BASE_URL`/`MEDIA_DOMAIN`.
5. **Méthode** : web via merge → CI → `deploy.yml` (ou pipeline staging). **Jamais** `git pull` /
   `--build`. **APK = rebuild manuel avec FLAG_SECURE ON** (ne pas livrer l'APK test flagsecure-off).

---

## 4. Validation

- **Backend** : suite complète **VERTE le 2026-07-27 — 1287 passed** (`pytest --create-db`, incl. fix adhésion), 4 warnings pré-existants (naive datetime, sans rapport).
- **Mobile** : `flutter test` 150 OK + `analyze` propre.
- **Frontends** : `tsc` portail + admin exit 0. `ruff` propre.

---

## 5. Hors périmètre / à suivre après livraison

- **G6b** : bouton « privilège » dans l'écran de validation admin (le comité approuve comme avant ;
  découvert + criticité déjà **visibles**, mais le flag privilège reste `false` tant que l'UI manque).
  Non bloquant — traçabilité en plus.
- **P2** (multi-voie cumulée) : non livré (structurant), à planifier.
- Affichage membre (mobile/portail) de la criticité/découvert : à compléter (G6b).

---

## 6. Check des flows de base (audit end-to-end, 2026-07-27)

Audit de cohérence (lecture seule) des 8 use cases, **après** les changements de gouvernance.

| # | Use case | Verdict |
|---|---|---|
| 1 | Adhésion → approbation → 3 frais → activation | ✅ OK (état ACTIF correct) — 1 risque **faible** cosmétique (cf. risques) |
| 2 | Épargne collecte → clôture fin de mois + commission 1 % | ✅ OK |
| 3 | Épargne classique → retrait (débité au paiement) | ✅ OK |
| 4 | Crédit auto-couverture / apport (senior_brc) | ✅ OK |
| 5 | Crédit avaliste | ✅ OK |
| 6 | Crédit campagne (membre + visiteur, frais sautés si 0) | ✅ OK |
| 7 | Contentieux / saisie multi-source | ✅ OK |
| 8 | Reconduction (uniquement à l'échéance) | ✅ OK |

**Points de vigilance vérifiés :**
- ✅ Le **plancher 30 % ne s'applique QU'À senior_brc** — campagne / avaliste / garantie matérielle ont leurs propres évaluateurs sans plancher apport (garde-fou cagnotte limité à senior_brc + avaliste). **Aucun blocage erroné.**
- ✅ Décomposition **gagé/découvert cohérente par voie** : auto-couvert 0 · apport 80 % · avaliste ≈0 · campagne/garantie 0.
- ✅ Chaque use case + Lot 0 + gouvernance couverts par des tests dédiés.

## 7. Risques de livraison (par gravité) — ACTIONS AVANT MISE EN PROD

- **🔴 ÉLEVÉ — Re-seed du schéma `loan_request` obligatoire.** Sans lui, `brc_proof_field_ids()` renvoie vide :
  pas de crash (dégradation gracieuse) mais **les pièces BRC ne sont plus routées vers la file de validation**
  et les libellés de la fiche disparaissent. → `python manage.py seed_form_schemas --force` **avant ouverture**.
- **🟠 MOYEN — Vérifier les 4 AppSettings gouvernance en prod** (le seed n'écrase PAS l'existant → vérifier les
  valeurs EFFECTIVES, pas seulement re-seeder) : `loans.eligibility.apport_rate=0.30`, `loans.apport.rate=0.20`,
  `loans.apport.min_available_rate`, `loans.interest_withheld_at_source=true`. Si une valeur legacy traîne, la
  règle 30/20/source n'est pas appliquée.
- ~~🟡 FAIBLE — Adhésion : primo-adhérent mal routé en reconduction~~ **✅ CORRIGÉ** (commit `cfccaa0`) :
  marqueur `Member.date_activation` + migration 0020 (backfill). Testé (primo → activation ; revenant → renouvellement).
- **🟡 FAIBLE — Docstring obsolète** (`savings/views.py:518` « débité à l'approbation ») : sans impact.

## 8. Go / No-Go

**GO livraison** côté code : suite backend **1285 verte**, 8 flows de base **OK**, clients (mobile/tsc) verts.
Les 2 risques ÉLEVÉ/MOYEN sont des **actions de déploiement** (re-seed + vérif settings), pas des bugs de code —
elles DOIVENT être faites au déploiement (cf. §3 + ci-dessus).
