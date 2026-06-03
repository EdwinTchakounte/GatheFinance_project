# Réalisé — Application mobile Gathé Finance

> **Espace sociétaire mobile** de la coopérative d'épargne et de crédit Gathé Finance.
> `gathe_finance` · Flutter · version `0.1.0+1`
> Document arrêté au **24 mai 2026**.

---

## 1. Périmètre livré

L'application mobile est l'**espace membre** (sociétaire). Elle couvre l'ensemble du
parcours d'un sociétaire : adhésion, épargne, cotisations, crédit, reconduction,
suivi et notifications. Toutes les règles financières sont alignées sur le
**Règlement Intérieur Gathé Finance 2025** (source de vérité).

### Modules fonctionnels (16 features)

| Module | Contenu livré |
|---|---|
| **auth** | Connexion, fiche membre, formulaire d'adhésion |
| **onboarding** | Écrans d'accueil première ouverture (vu/non-vu persistant) |
| **splash / shell** | Démarrage, navigation principale (bottom nav) |
| **home** | Tableau de bord membre, solde héros (count-up), dépôt classique + dépôt rapide |
| **savings** | Épargne : consultation solde, dépôt, historique des transactions |
| **contributions** | Cotisations journalières (1 000 / jour, Art. 4) |
| **credit / loans** | Demande de crédit, échéancier, remboursement, **reconduction** (Art. 10-11) |
| **booklet** | Commande de carnet (1 000, Art. 4) |
| **notifications** | Liste, marquage lu / tout lu |
| **profile** | Mes informations, changement de mot de passe |
| **preferences / security** | Réglages et sécurité |
| **states** | Écrans d'états (relevés / situations) |
| **help** | Page contact / assistance |

---

## 2. Conformité au Règlement Intérieur 2025

Les règles métier sont centralisées dans
`lib/features/loans/domain/loan_terms.dart` — **miroir mobile** du backend
`apps_coop/loans/terms.py`. Chaque constante cite son article.

| Règle | Article | Implémentation mobile | Valeur |
|---|---|---|---|
| Intérêt crédit (flat, par transaction) | Art. 5 | `kLoanInterestRate` | **10 %** |
| Paliers de durée (8 tranches, 2→9 mois) | Art. 7 | `kLoanDurationTiers` + `durationMonthsFor()` | 5 000 → 9 paliers |
| Modalités de remboursement | Art. 8 | `PaymentModality` (journalier/hebdo/mensuel) | 30 / 4 / 1 par mois |
| Reconduction — prorogation fixe | Art. 10 | `kRenewalExtraMonths` | **+1 mois** |
| Reconduction au comptant | Art. 11 | `kRenewalRateComptant` | **10 %** du capital restant |
| Reconduction reportée | Art. 11 | `kRenewalRateReporte` | **15 %** du capital restant |
| Pénalité de retard | Art. 12 | `kLatePenaltyRate` + `latePenalty()` | **50 %** des intérêts dus |
| Intérêt épargne mensuel | Art. 4 | `kSavingsMonthlyRate` | **1 % / mois** |
| Cotisation journalière | Art. 4 | `kDailyContribution` | **1 000** |

**Garde-fous métier intégrés :**
- Montant tombant dans un « trou » entre deux paliers → on retient le **palier
  supérieur** (durée plus longue, protège l'emprunteur).
- Reconduction : pas d'intérêt sur intérêt — le taux porte **uniquement** sur le
  capital restant dû.
- Reconduction limitée à **une seule fois** (Art. 10/11).

---

## 3. Architecture & qualité

- **Clean architecture** par feature : `domain` (entités, use cases, repositories)
  → `data` (datasources, repository impl) → `presentation` (pages, widgets, state).
- **Injection de dépendances** centralisée (`lib/core/di`).
- **Design system Paysika** unifié : `PaButton`, `PaErrorState`, `PaStatusChip`,
  `PaAvatar`, `PaHeroBalance` (animation count-up). Les 4 écrans legacy ont été
  migrés vers ce système.
- **Polices bundlées hors-ligne** (Sora / Inter / Lora / JetBrains) — aucun appel
  réseau Google Fonts, pour fonctionner sur device de test sans internet.
- **Modales** : hauteur plafonnée à 90 % de l'écran (`maxHeight`) sur 8 feuilles
  (demande de crédit, reconduction, remboursement, dépôts, adhésion, carnet,
  profil, mot de passe) — correction du contenu qui « remontait trop haut ».

### Indicateurs qualité (mesurés le 24/05/2026)

| Indicateur | Résultat |
|---|---|
| Tests automatisés | **66 / 66 verts** (23 fichiers de test) |
| `flutter analyze lib` | **0 erreur · 0 warning** |
| Lint info restant | 166 (cosmétique : virgules de fin — `require_trailing_commas`) |

Couverture de test : use cases (auth, épargne, crédit, reconduction,
remboursement, carnet, notifications, onboarding), repository impls, et widgets
clés (login, notifications, deposit sheet, tuiles d'échéance / transaction,
montants, loader de marque).

---

## 4. Point d'attention — état d'intégration

⚠️ **L'app mobile fonctionne aujourd'hui sur des datasources *mock*.**

- Les calculs de `loan_terms.dart` sont une **ré-implémentation mobile** des
  règles, utilisée pour l'affichage et les simulations locales. Ils **concordent**
  actuellement avec le backend et le Règlement (vérifié).
- Le **backend Django reste la seule source de vérité** pour les calculs réels
  (intérêts, pénalités, contentieux 90 j, crons). Côté serveur : zéro collision,
  calculs idempotents, 136 tests verts.
- **Reste à faire** pour la mise en production de bout en bout :
  1. Brancher les `*_remote_datasource` mobiles sur l'API réelle (remplacer les mocks).
  2. Ajouter le flux **demande de retrait** côté membre (le backend est déjà prêt :
     `request_withdrawal` + accusé de réception e-mail).

Une fois le branchement effectué, le mock mobile s'efface au profit des valeurs
serveur — pas de divergence possible.

---

## 5. Récapitulatif

| | |
|---|---|
| Modules livrés | **16 features**, parcours sociétaire complet |
| Conformité Règlement 2025 | **100 %** (9 règles financières alignées, articles cités) |
| Tests | **66/66 verts** · analyze **0/0** |
| Design | Système Paysika unifié, polices hors-ligne |
| Maturité | Front complet sur mocks — **prêt pour branchement API** |
