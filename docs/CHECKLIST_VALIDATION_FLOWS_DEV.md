# Checklist de validation des flows — horus-lab (dev)

Objectif : valider **toutes les actions de base** et confirmer leur effectivité, sur le serveur de dev
(`*.gathe-finance.horus-lab.com`), **mobile + web (portail membre + dashboard admin)**.

Convention : `[ ]` à tester · noter **OK** / **KO** + détail. Tout **KO** → je corrige le code.

---

## A. Compte & session (mobile + portail)
- [ ] Adhésion (formulaire vitrine/portail) → création dossier
- [ ] Activation du compte (mail mot de passe / première connexion)
- [ ] Login membre (mobile) + login membre (portail) — mêmes identifiants
- [ ] Session 30 min glissante (pas de déconnexion intempestive)
- [ ] Déconnexion / redirection login à l'expiration

## B. Accueil / patrimoine (mobile + portail)
- [ ] Soldes par poche (épargne classique, placement, collecte) corrects
- [ ] Solde total cohérent (pas de double-comptage placement)
- [ ] Montants formatés (pas de « XAF XAF », nom = « nom + prénom »)

## C. Épargne
- [ ] Versement épargne — canaux dispo + **minimum 1000** appliqué (mobile + portail)
- [ ] Placement (épargne placée) — création + restitution date fixe
- [ ] Retrait épargne : initiation → approbation admin → **débit AU paiement** seulement
- [ ] Retrait : montant réservé (net du réservé) affiché correctement
- [ ] Payout échoué = zéro débit

## D. Collecte journalière
- [ ] Cotisation collecte (versement)
- [ ] Commission 1 % à la clôture mensuelle (par défaut)
- [ ] Fin de mois : « versement sur mon compte » (cash / mobile money / épargne) **persisté** (mobile + portail)

## E. Crédit (mobile + portail + admin)
- [ ] Demande crédit — les **5 voies** (senior/BRC, avaliste, garantie matérielle, campagne, ancien sous-couvert)
- [ ] Voie **choisie** respectée (pas de vol par priorité)
- [ ] Garde-fou apport : rejet auto si cagnotte dispo < 10 % ; apport 20 % indicatif
- [ ] Gel de l'apport à l'acceptation + motif affiché ; transfert du gelé pour rembourser
- [ ] Frais d'étude : paiement Mobile Money **et** « par épargne »
- [ ] Combinaisons BRC+avaliste / BRC+garantie
- [ ] Validation (double approbation) → frais → **décaissement manuel** (mode réception affiché à l'agent)
- [ ] Remboursement (partiel + solde → clôture) cross-canal
- [ ] Reconduction uniquement à terme (date butoir) ; 1 seule fois ; 1 crédit à la fois
- [ ] Crédit clôturé ne bloque pas une nouvelle demande ; libellé « Crédit n°X »

## F. Transferts (mobile + portail)
- [ ] Transfert vers un crédit (pas de « XAF XAF »)
- [ ] Transfert entre poches / comptes (si applicable)

## G. Profil / sécurité (mobile)
- [ ] Changement photo de profil effectif
- [ ] Nom affiché « nom + prénom » partout
- [ ] Sécurité (PIN / mot de passe)

## H. Social / contenu (mobile + portail)
- [ ] Campagnes (liste, détail, candidature — membre & non-membre)
- [ ] Fil d'actualités / articles (likes, commentaires)
- [ ] Support en ligne (chat membre ↔ coop)
- [ ] Notifications (poll + à onglets)

## I. Dashboard admin (web)
- [ ] Login + RBAC (rôles = bundles d'onglets, enforcement)
- [ ] Membres : annuaire, fiche « Voir plus », fiche d'adhésion
- [ ] Adhésions : pipeline, validation → compte actif au paiement
- [ ] Crédit : demandes, validation, frais (= frais campagne), décaissement manuel, **invalidation paiement**, **suppression tracée**
- [ ] Paiements : ledger, invalidation (contre-passation)
- [ ] Retraits : ligne → fiche membre, validation → paiement
- [ ] Campagnes : création (min/max, fee 0/500), images vitrine, candidatures
- [ ] CMS/blog : « Ouvrir dans Wagtail » OK, articles i18n (FR/EN)
- [ ] Emails : liens ouvrent une route portail existante (pas de 404)
- [ ] AppSettings / planificateurs (Django Q schedules)

---

## Modes d'exécution
1. **Tu pilotes** (device mobile + portail/admin) → tu notes OK/KO ici → je **corrige** chaque KO dans le code.
2. **Validation API** (je pilote) : donne-moi un **compte de test** (email + mot de passe) → je scripte les flows clés contre `api.gathe-finance.horus-lab.com`.
3. **Je pilote l'UI** : nécessite `adb` (device branché) ou l'extension navigateur connectée — actuellement indisponibles ici.

> Rappel : horus-lab tourne le code de la branche `staging` (images `:staging`). Tout bug corrigé → merge `staging` → redéploiement auto recette.
