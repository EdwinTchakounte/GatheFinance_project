# Live-test mobile — 2026-07-23

Test réel sur **téléphone physique** (TECNO KM5), build **release de TEST**
(FLAG_SECURE désactivé temporairement pour les captures), pointant la **prod à
jour** (`api.gathe-finance.horus-lab.com`). Compte : `etchambatchakounte@gmail.com`
(« Edwin »).

> ⚠️ Le build de test a **FLAG_SECURE désactivé** (changement local **non
> commité**). À réactiver avant toute version de livraison.

---

## ✅ Vérifié EN LIVE — formulaire de demande de crédit

| Point | État |
|---|---|
| Card « Classique » retirée du carrousel | ✅ (carrousel = Avaliste · Campagne · Garantie) |
| Voie par défaut via le FAB « + Nouvelle demande » | ✅ (ouvre le formulaire) |
| **Bouton retour ←** en tête du formulaire | ✅ ajouté **et fonctionne** (ferme le formulaire) |
| **Note frais SANS montant** | ✅ « Des frais d'étude de dossier peuvent s'appliquer, à régler après acceptation. Ils peuvent être offerts pour une demande en campagne. » |
| **Zéro duplication** parcours/CGA/BRC | ✅ « Votre parcours de formation », « Adhésion CGA », « Rattachement BRC » chacun **une seule fois** |
| Récap remboursement (montant net, intérêts 10 % au décaissement) | ✅ cohérent |
| Sécurité : solde masqué à l'accueil (révéler = PIN) | ✅ |

---

## ⚠️ En attente d'une action prod

- **Section « Rattachement Broad Range Consulting » encore visible** : sa
  suppression est un changement **de code non déployé** ; l'app lit le schéma
  servi par la prod. Pour la faire disparaître :
  1. Committer + déployer la suppression de `profil_brc` (`seed_form_schemas.py`).
  2. Republier : `seed_form_schemas --force --only loan_request` sur le VPS.

---

## ⏳ Reste à tester (crée de vraies écritures + PIN à la confirmation)

- **Versement épargne** (dépôt MoMo → validation MoMo + PIN sur le téléphone).
- **Retrait** → doit afficher la carte « en attente », puis « Approuvée · remise
  espèce · en attente » après validation admin → **vérifier le fix d'affichage**
  (montant EN HAUT, statut EN DESSOUS, plus de chevauchement).
- **Transfert**.
- **Crédit par voie** (soumission Avaliste / Campagne / Garantie + étape frais).
- **Remise** (remboursement) et **Reconduction** — nécessitent un crédit actif
  (le compte Edwin n'en a pas actuellement).
- **Restitution de placement** (côté admin) — intérêt à taux fixe + ligne capital.

---

## Changements de code de cette session PAS ENCORE commités/déployés

Faits après la PR #43 (mergée), à regrouper dans un prochain commit :

| Fichier | Changement | Actif via |
|---|---|---|
| `mobile/.../app_fr.arb` + `app_en.arb` (+ gen) | note frais sans montant | APK (✅ dans le build test) |
| `mobile/.../loan_request_sheet.dart` | bouton retour | APK (✅) |
| `mobile/.../home_page.dart` | carte retrait accueil : montant haut / statut bas | APK (✅) |
| `mobile/.../states_page.dart` | ligne retrait : montant haut / statut bas | APK (✅) |
| `mobile/.../credit_page.dart` | carte demande crédit : montant haut / statut bas | APK (✅) |
| `backend/.../seed_form_schemas.py` | section `profil_brc` retirée | **reseed prod** |
| `mobile/android/.../MainActivity.kt` | FLAG_SECURE OFF (**TEST ONLY**) | ⚠️ NE PAS committer/livrer |

---

## Setup live-test (pour référence)

- `adb` : `~/Android/Sdk/platform-tools/adb` — la liaison USB de ce câble est
  **instable** (ré-énumérations, décrochages). Utiliser un **câble data fiable**.
- Screencap : possible **uniquement** avec FLAG_SECURE désactivé (sinon écran noir).
- Login / PIN : **saisis par l'utilisateur** (règle de sécurité — jamais par l'assistant).
