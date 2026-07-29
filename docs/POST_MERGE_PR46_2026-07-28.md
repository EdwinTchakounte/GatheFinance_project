# Post-déploiement — merge PR #46 (2026-07-28)

## Statut déploiement (2026-07-28)

| Étape | État |
|---|---|
| Merge PR #46 → `main` (squash `78b75c1`) | ✅ fait |
| CI `main` (backend pytest+ruff / frontend lint+typecheck / mobile analyze+test) | ✅ success |
| Build + push images GHCR (backend, site, admin, portal) | ✅ success |
| **Deploy to prod — VPS Contabo** (`Deploy on Contabo VPS`) | ✅ **success** |
| Commandes données + réglages (ci-dessous §1–§2) | ⬜ à lancer sur le serveur |
| Rebuild APK mobile (§5) | ⬜ à faire |
| Rattrapage GF-CR-2026-0005 (§4) | ⬜ à faire après les seeds |
| Smoke test prod (§3) | ⬜ à faire |

Le **web est déployé en prod**. Restent les 4 actions manuelles cochées ⬜ ci-dessus.

---

Runbook à lancer **après** le merge de la PR #46 (`feat/credit-hardening-campaigns-cms-emails → main`).

La CI déploie le web automatiquement (merge → build GHCR → `deploy.yml` → VPS). Restent les **données** (migrations + seeds) et quelques **réglages**, à faire sur le serveur. Le **mobile** est un rebuild APK **manuel** séparé.

> Rappel prod : jamais `git pull` ni `--build` sur le serveur ; le déploiement passe par la CI. Ne jamais lancer `docker system prune --volumes`.

---

## 1. Migrations + seeds (dans le conteneur backend)

> ⚠️ **Piège à éviter** : ne colle PAS le `docker exec … bash` ET les commandes `python`
> dans le même bloc d'un coup. La 1ʳᵉ ligne ouvre le shell du conteneur et les lignes
> suivantes sont **perdues** (avalées au démarrage de bash) → aucune sortie, rien ne tourne.
> **Étape 1 : entrer dans le conteneur. Étape 2 (une fois le prompt `root@…:/app#` affiché) :
> lancer les commandes, idéalement UNE PAR UNE.**

**Étape 1 — entrer dans le conteneur :**
```bash
ssh root@81.0.246.144
docker exec -it gathe-finance-prod-backend-1 bash
```

**Étape 2 — une fois le prompt `root@…:/app#` affiché, lancer une par une :**
```bash
python manage.py migrate
python manage.py seed_form_schemas --force
python manage.py bootstrap_site
python manage.py seed_blog
python manage.py seed_email_templates --force
```

> 🔴 `seed_form_schemas --force` est **obligatoire** : sans lui, les pièces BRC ne remontent plus à la file de validation.
> `bootstrap_site` + `seed_blog` réparent le CMS Wagtail (articles / éditeur), `seed_email_templates --force` corrige les liens des emails.

**Sorties attendues (signes de réussite) :**

| Commande | Sortie OK |
|---|---|
| `migrate` | `Applying … OK` ou `No migrations to apply` — aucune erreur |
| `seed_form_schemas --force` | (ré)écriture des schémas, pas de traceback |
| `bootstrap_site` | Locales fr/en + HomePage + BlogIndex + Site, **fin sans 500** (dé-silencé exprès) |
| `seed_blog` | articles seedés (fr/en) |
| `seed_email_templates --force` | ~15 templates (ré)écrits |

⚠️ Point sensible = **`bootstrap_site`** : s'il crache un traceback, c'est le bug CMS Wagtail → le capturer en entier pour correctif.

Ce merge n'ajoute **aucune nouvelle migration** côté lot intégrité (aucun modèle modifié : `en_attente_decaissement` et `montant_gele_demandeur` existaient déjà). `migrate` reste requis pour les migrations du reste du lot (ex. `members 0020`).

---

## 2. Réglages (AppSettings gouvernance / apport / emails)

Dans l'admin (Paramètres) ou `python manage.py shell`, s'assurer que :

| Réglage | Valeur attendue |
|---|---|
| `loans.eligibility.apport_rate` | `0.30` |
| `loans.apport.rate` | `0.20` |
| `loans.apport.min_available_rate` | `0.10` |
| `loans.interest_withheld_at_source` | `true` |
| `notifications.admin_url` | domaine admin (sinon lien admin des emails → fallback portail) |
| `collecte.monthly.commission_rate` | `0.01` (1 %) |

> `seed_app_settings` **n'écrase pas** les valeurs existantes : un réglage à changer en prod se fait en `update_or_create` manuel, pas en re-seed.

---

## 3. Smoke test (validation « en vrai »)

- Vitrine / portail / admin répondent (200).
- Un article de blog s'ouvre (vitrine) + l'éditeur Wagtail ne renvoie pas 500.
- Un email récent (frais payés / retrait / reconduction) ouvre une **route portail existante** (pas de 404).
- **Crédit non décaissé** : sur un crédit `en attente — argent pas encore versé`, le remboursement et la reconduction sont **refusés** ; le décaissement reste possible (rattrapage).
- **Gel** : détail crédit affiche « Gelé (demandeur) » ≤ épargne réelle, et une ligne « Déficit de collatéral » si l'épargne a fondu.
- Carte admin « Exposition au découvert » affiche l'encours.

---

## 4. Rattrapage du crédit coincé GF-CR-2026-0005

Ce crédit est resté **clôturé mais non décaissé** (argent jamais versé). Le décaissement est désormais autorisé dessus :

- Back-office → Crédits → GF-CR-2026-0005 → **« Payer maintenant »** (il rebascule ACTIF et verse le net), **ou** annuler proprement si le crédit ne doit pas être honoré.

---

## 5. Mobile (séparé du web)

Le déploiement web ne met pas à jour l'app. Pour diffuser les correctifs déjà mergés (doublon « XAF XAF », en-tête nom, envoi prénom/nom séparés) :

```bash
cd mobile
flutter build apk --release
```

> Piège RAM Gradle : baisser `-Xmx8G` → `2G` et couper le daemon temporairement si le build sature la mémoire.

---

Contexte complet du lot : voir la PR #46 et `docs/COMMANDES_POST_DEPLOY_STAGING.md`.
