# Audit parité Web (portail membre) ↔ Mobile Android + flow par usecase

**Date :** 2026-07-24
**Périmètre :** crédit · collecte · épargne classique · placement (prêteur)
**Méthode :** 4 audits de flow en parallèle (backend Django + mobile Flutter + portail Next.js + vitrine), lecture seule.

---

## Verdicts par usecase

| Usecase | Verdict | Parité mobile↔portail | Bugs bloquants |
|---|---|---|---|
| **Collecte** | ✅ OK | Complète (6 actions) | Aucun |
| **Épargne classique** | ✅ OK | Complète | Aucun |
| **Crédit** | ⚠️ OK avec écarts | Quasi-complète | 1 flow incomplet (contre-proposition) |
| **Placement** | ⚠️ Écarts | **Rompue** (gestion prêteur) | Aucun, mais affichage obsolète |

Le **fond métier est solide partout** : dissociation des soldes (collecte / libre / placement / gelé) sans double-comptage, retrait débité **au paiement** avec réservation, débit-au-paiement idempotent, imputation carnet au dernier commandé, commission collecte 1 %, intérêts à la source 10 %, 4 voies crédit avec choix respecté, funding + libération de tranches à la clôture.

---

## 🔴 P1 — Le plus important : la copie « 50/50 » est OBSOLÈTE partout

Depuis le 2026-07-24 (chantier 1, PR #45), la rémunération prêteur = **k × contribution** (`loans.lender.interest_rate`, défaut **0.03 = 3 %**). L'ancien partage 50/50 par quote-part est abandonné. Or l'ancienne promesse « 50 % des intérêts » subsiste :

- **Mobile** — carte opt-in `lender_page.dart:311-312` (« 50/50 »), et `my_lender_payouts_page.dart:175-176` affiche `part {quote_part}%` → chiffre **trompeur** (quote_part = fraction financée, plus la base du calcul).
- **Portail** — `preteur/page.tsx:90-91` et `188-189` (« 50 % » / « partage 50/50 »).
- **Doc** — `architecture/BUSINESS_RULES_2026.md` l.320-328, 498, 742, 754.
- **API** — `loans/views.py:2140` renvoie encore `quote_part` (legacy, alimente le mobile).
- **Docstring** — `payments/services.py:518-519` référence `lender.interest_share_rate` abandonné.

➡️ **Impact captures d'écran :** un membre prêteur verrait « 50 % » à l'écran alors qu'il touche 3 %. À corriger AVANT de capturer.

---

## Écarts de parité réels (mobile vs portail)

| # | Écart | Mobile | Portail | Sévérité | Nature |
|---|---|---|---|---|---|
| A | **Gestion convention prêteur** (opt-in explicite A, révoquer, tranches par statut) | ❌ route retirée (`app_router.dart:317`) | ✅ `preteur/page.tsx` | Moyenne | **Choix design** (funding admin-piloté) → à trancher : retirer côté portail aussi, ou restaurer mobile |
| B | **Rembourser sur épargne depuis l'écran Crédit** | ❌ (seulement depuis Home) | ✅ `/credit` | Moyenne | Découvrabilité |
| C | **Historique paginé complet** | ❌ snapshot + PDF only | ✅ `/savings/transactions/` paginé | Moyenne | Le membre mobile ne remonte pas au-delà de la fenêtre snapshot |
| D | Frais d'étude 3 canaux en inline | inline = MoMo only | ✅ 3 canaux partout | Faible | |
| E | Masquer un crédit clôturé (soft-hide) | ✅ | ❌ | Faible | |
| F | Page « États » pédagogique (cycle retrait) | ✅ | ❌ (soldes inline sans bloc pédago) | Cosmétique | |

---

## Flow incomplets / durcissements (des 2 côtés)

| # | Problème | Détail | Sévérité |
|---|---|---|---|
| 1 | **Contre-proposition = cul-de-sac** | Statut `EN_ATTENTE_ACCEPTATION_MEMBRE` posable par l'admin, mais **aucun endpoint membre accept/refus** et aucune transition sortante. Bloque aussi toute nouvelle demande (`views.py:170`). | Moyenne |
| 2 | **Min versement ≠ 1000 partout** | Backend n'impose que `>0` ; mobile 100/500, portail 500. Règle « 1000 partout » non enforced. | Moyenne |
| 3 | **Placement auto-signe la convention** | Dépôt `is_placement` crée un `LenderConsent` en silence et **ré-active un consentement révoqué** sans re-signature (`payments/services.py:565-577`) vs §6 « convention signée requise ». | Moyenne |
| 4 | **Texte « bloqué 12 mois » faux** | Restitution en réalité à date fixe (défaut 1er janvier, `placement_maturity.py:26`). Mobile `deposit_sheet.dart:231,446,915` + portail `epargne/page.tsx:278`. | Moyenne |
| 5 | Règles collecte codées en dur | mobile `collecte_terms.dart` + portail `epargne/depot` hardcodent min 1000 / 30j / step 50 au lieu de `GET /savings/info/`. | Faible |
| 6 | Plancher retrait backend laxiste | `serializers.py:220` `min_value=1` vs 500 imposé clients. | Faible |
| 7 | `/savings/info/` renvoie `min_amount_xaf: 100` | vs enforcement réel 1000 (`views.py:134`). Non consommé, mais trompeur. | Faible |

---

## Note : pas de virement membre↔membre
Le « transfert » mobile (`transfer_sheet.dart`) = **remboursement de crédit depuis l'épargne**, pas un virement entre membres. Aucun virement membre↔membre n'existe (à créer seulement si attendu).

---

## Recommandation d'ordre (avant captures d'écran)

1. **P1 — aligner la copie « 50/50 » → « k × contribution / 3 % »** (mobile + portail + doc + retirer l'affichage `quote_part %`). Indispensable pour des captures correctes ; complète le chantier 1.
2. **Trancher l'écart A** (espace prêteur) : retirer `/preteur` du portail (aligner sur l'admin-piloté) OU restaurer la route mobile.
3. Écarts B (repay sur écran crédit mobile) + textes « 12 mois » (#4).
4. Durcissements min-versement 1000 (#2) + contre-proposition (#1) : décisions produit.
