# Rapport d'audit de déploiement — Gathe Finance

> **Coopérative d'épargne et de crédit — Cameroun**
> Audit post mise-en-ligne sur VPS Contabo

---

| **Émis par**         | **Groupe Horus-lab** — Cellule Audit & Recette |
|----------------------|------------------------------------------------|
| **Référence**        | `AUDIT-GF-2026-06-23-DEP`                      |
| **Date d'émission**  | 23 juin 2026                                   |
| **Type d'audit**     | Post-déploiement — Infra & applicatif          |
| **Périmètre**        | Stack production (5 sous-domaines + backend)   |
| **Environnement**    | Contabo VPS — `gathe-finance.horus-lab.com`    |
| **Niveau**           | Production réelle                              |
| **Verdict global**   | **🟢 Opérationnel avec 3 réserves bloquantes** |

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Méthodologie](#2-méthodologie)
3. [Périmètre audité](#3-périmètre-audité)
4. [Synthèse des constats](#4-synthèse-des-constats)
5. [Détail par plateforme](#5-détail-par-plateforme)
   - [5.1 Vitrine publique](#51-vitrine-publique)
   - [5.2 Portail membre](#52-portail-membre)
   - [5.3 Console d'administration](#53-console-dadministration)
   - [5.4 API REST](#54-api-rest)
   - [5.5 CMS Wagtail](#55-cms-wagtail)
   - [5.6 Application mobile Flutter](#56-application-mobile-flutter)
6. [Infrastructure et exploitation](#6-infrastructure-et-exploitation)
7. [Tableau des findings classés par sévérité](#7-tableau-des-findings-classés-par-sévérité)
8. [Recommandations priorisées](#8-recommandations-priorisées)
9. [Annexes](#9-annexes)

---

## 1. Résumé exécutif

### 1.1 Contexte de l'audit

Le **Groupe Horus-lab**, agissant en qualité d'auditeur post-déploiement,
a procédé le **23 juin 2026** au contrôle complet de la stack **Gathe Finance**
fraîchement mise en production sur le VPS Contabo `81.0.246.144`.

L'objectif était de **valider l'opérationnabilité réelle des cinq plateformes
publiques** (vitrine, portail membre, console d'administration, API, CMS Wagtail)
plus le **client mobile Flutter**, et de produire un état des lieux exploitable
par les équipes Dev et Ops pour piloter les corrections résiduelles avant
ouverture grand public.

### 1.2 Verdict synthétique

| Indicateur | Note | Commentaire |
|---|---|---|
| **Disponibilité réseau** | 🟢 5/5 | Les 5 sous-domaines répondent en HTTPS valide |
| **Validité certificats TLS** | 🟢 | Let's Encrypt actifs sur tous les vhosts |
| **Santé backend Django** | 🟢 | Healthcheck `/healthz/` = 200, conteneur `healthy` |
| **Santé Postgres** | 🟢 | DB initialisée, conteneur `healthy` |
| **Routage nginx mutualisé** | 🟢 | 4 projets en cohabitation propre |
| **UX console admin** | 🟠 | Auth gate hangs à `/` (loading infini) |
| **UX portail membre** | 🟠 | Routes non préfixées renvoient 404 |
| **CMS Wagtail (root cms.*)** | 🟠 | Redirige vers vitrine (302) |
| **Build mobile prod (AAB)** | 🟢 | Signé, taille 53,7 Mo, prêt Play Store |
| **Mobile suite de tests** | 🟢 | 118/118 verts |
| **CI/CD GHCR** | 🟢 | Pipeline `ci.yml` + `deploy.yml` armés |

**Score global : 8/11 — Opérationnel avec réserves.**

### 1.3 Faits saillants

- ✅ **Mise en service réussie** : les images GHCR sont déployées, les
  certificats émis, et le moteur métier (épargne, crédit, paiement, cron)
  est joignable.
- ⚠️ **Trois irritants UX bloquent un parcours utilisateur fluide** :
  l'admin reste bloquée en *"Chargement…"* sur `/`, le portail ne gère pas
  les URL non préfixées, et le sous-domaine `cms.*` à la racine renvoie sur
  la vitrine au lieu d'afficher un message contrôlé.
- ⚙️ **Trois actions tierces** restent à exécuter par l'exploitant :
  configurer le webhook Tara, vérifier le domaine expéditeur Brevo, et
  publier l'AAB sur Play Console.
- 🛡️ **Aucune vulnérabilité critique détectée** sur la base des contrôles
  externes effectués (la revue sécurité approfondie a été produite dans
  `AUDIT_2026-06-20.md`).

---

## 2. Méthodologie

### 2.1 Approche

Audit en **boîte grise**, combinant :

- **Inspection externe** : requêtes HTTP/S vers chacun des cinq vhosts,
  contrôle des codes retour, des en-têtes (TLS, sécurité, redirections),
  du temps de réponse, du contenu rendu (titre HTML, blocs visibles).
- **Lecture des fichiers de configuration** : `docker-compose.prod.yml`,
  `docker-compose.nginx-external.yml`, `.env.prod` (anonymisé), config
  nginx mutualisée `/home/deploy/afrikamode/backend/deploy/nginx/default.conf`,
  pipeline CI `.github/workflows/ci.yml` et CD `.github/workflows/deploy.yml`.
- **Lecture du code applicatif** côté Next.js (admin + portail) et côté
  Django/DRF pour rapprocher les comportements observés et les chemins
  d'exécution.
- **Exécution de la suite de tests mobile** (`flutter test`) et de
  l'analyseur statique (`flutter analyze`) sur la branche déployée.
- **Build AAB de production** avec `--dart-define=API_BASE_URL=https://api.gathe-finance.horus-lab.com`.

### 2.2 Critères d'évaluation

Chaque plateforme a été notée sur 4 dimensions :

| Dimension | Question contrôlée |
|---|---|
| **Disponibilité** | L'URL répond-elle en HTTPS valide ? |
| **Contenu rendu** | Le HTML / JSON livré correspond-il à l'attendu fonctionnel ? |
| **Cohérence routage** | Les routes alternatives (locales, sous-pages clés) renvoient-elles 200 ? |
| **UX premier accès** | Un visiteur non-authentifié obtient-il un état utilisable ? |

### 2.3 Limites de l'audit

- Les contrôles fonctionnels métier (versement, demande de crédit, décision
  comité, webhook Tara) n'ont **pas** été rejoués end-to-end faute de compte
  membre actif côté production. Ils relèveront d'une recette utilisateur
  séparée.
- Les contrôles côté serveur (logs runtime, métriques système) ont reposé
  sur les retours de l'exploitant. L'auditeur n'a pas eu d'accès SSH direct
  durant l'audit.
- Les tests de charge et la résilience (chaos engineering) sont hors
  périmètre.

---

## 3. Périmètre audité

### 3.1 Plateformes

| # | Sous-domaine | Rôle | Image / Service |
|---|---|---|---|
| 1 | `gathe-finance.horus-lab.com` | Vitrine publique Next.js | `ghcr.io/.../site:latest` |
| 2 | `portail.gathe-finance.horus-lab.com` | Espace membre Next.js | `ghcr.io/.../portal:latest` |
| 3 | `admin.gathe-finance.horus-lab.com` | Console staff Next.js | `ghcr.io/.../admin:latest` |
| 4 | `api.gathe-finance.horus-lab.com` | API REST Django + DRF | `ghcr.io/.../backend:latest` |
| 5 | `cms.gathe-finance.horus-lab.com` | Wagtail (édition contenus) | `ghcr.io/.../backend:latest` |

### 3.2 Topologie infrastructure

```
                       Internet (HTTPS 443)
                              │
                              ▼
                  ┌────────────────────────┐
                  │  backend-nginx-1       │  Reverse-proxy mutualisé (host)
                  │  nginx:alpine          │  4 projets cohabitent
                  └───┬────────────────────┘
                      │ proxy_pass (réseau Docker partagé "backend_default")
       ┌──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
  gathe-site:3000  gathe-portal:    gathe-admin:   gathe-backend:8000
  (Next.js SSR)    3000             3000            (Django + Wagtail)
                                                   │
                                                   ▼
                                              gathe-db:5432
                                              (Postgres 16)
                                                   │
                                                   ▼
                                              qcluster (django-q2)
                                              backup (pg_dump cron)
```

### 3.3 Services tiers branchés

| Service | Statut | Action requise |
|---|---|---|
| **Brevo** (e-mails transactionnels) | Configuré (`BREVO_API_KEY` posée) | Vérifier domaine expéditeur dans Brevo |
| **Tara MoMo** (paiements) | Configuré (`TARA_API_KEY` + secret webhook) | **Webhook URL à déclarer dans dashboard Tara** |
| **GitHub Container Registry** | Pipeline actif | 4 images publiées à chaque push `main` |
| **Let's Encrypt** | 5 certificats actifs | Renouvellement auto par certbot |
| **Play Console** | AAB prêt | **Upload manuel restant** |

---

## 4. Synthèse des constats

### 4.1 Carte de chaleur

| Plateforme | Disponibilité | Contenu | Routage | UX 1er accès | **Note** |
|---|:---:|:---:|:---:|:---:|:---:|
| Vitrine | 🟢 | 🟢 | 🟢 | 🟢 | **A** |
| Portail membre | 🟢 | 🟢 | 🟠 | 🟢 | **B** |
| Console admin | 🟢 | 🟢 | 🟠 | 🟠 | **C+** |
| API REST | 🟢 | 🟢 | 🟢 | 🟢 | **A** |
| CMS Wagtail | 🟢 | 🟠 | 🟠 | 🟠 | **B−** |
| Mobile (build) | 🟢 | 🟢 | 🟢 | 🟢 | **A** |

### 4.2 Trois irritants prioritaires

> **F-01 · MAJEUR** — La console d'administration affiche *"Chargement…"*
> indéfiniment pour un visiteur non authentifié sur `/` et `/dashboard`.
> L'auth gate ne route pas vers `/login` automatiquement.

> **F-02 · MAJEUR** — Le portail membre ne sert que les routes préfixées
> `/fr` ou `/en`. Les chemins `/login` et `/dashboard` retournent 404,
> ce qui complique les liens entrants et les redirections post-paiement.

> **F-03 · MINEUR** — Le sous-domaine `cms.gathe-finance.horus-lab.com/`
> à la racine renvoie une **redirection 302 vers la vitrine** au lieu
> d'un message contrôlé "Console d'édition réservée à `/admin/`".

---

## 5. Détail par plateforme

### 5.1 Vitrine publique

**`https://gathe-finance.horus-lab.com/`**

| Paramètre | Valeur observée |
|---|---|
| Code HTTP | `200 OK` |
| Titre HTML | `Gathe Finance — Coopérative d'épargne et de crédit au Cameroun` |
| Poids HTML | 197 942 octets |
| Temps de réponse | 1,73 s (cold) |
| Server header | `nginx/1.29.8` |
| TLS | Let's Encrypt valide |

**Constats**

- 🟢 Rendu Next.js complet, polices Sora/Inter pré-chargées, images
  optimisées via `_next/image`.
- 🟢 Locale FR détectée correctement, contenu institutionnel cohérent.
- 🟢 Le sous-domaine racine sert bien le projet `site:latest`.

**Verdict** : **Conforme**. Aucune réserve.

---

### 5.2 Portail membre

**`https://portail.gathe-finance.horus-lab.com/`**

| Paramètre | Valeur observée |
|---|---|
| Code HTTP `/` | `200 OK` |
| Code HTTP `/fr` | `200 OK` |
| Code HTTP `/login` | **`404 Not Found`** |
| Code HTTP `/dashboard` | **`404 Not Found`** |
| Titre HTML | `Gathe Finance · Espace membre` |
| Server header | `nginx/1.29.8` |

**Constats**

- 🟢 La racine répond, l'application charge le shell next-intl.
- 🟠 **Toutes les routes fonctionnelles vivent sous `/[locale]/...`.**
  Les chemins non préfixés (`/login`, `/dashboard`, `/savings`,
  `/loans`) retournent 404 systématiquement.
- 🔍 Origine probable : le routeur next-intl n'expose pas de fallback
  côté serveur, et il n'existe pas de rewrite middleware redirigeant
  `/<path>` vers `/fr/<path>`.

**Impact métier**

- Les e-mails transactionnels (welcome, décaissement crédit, retrait)
  qui contiennent des liens non préfixés tomberont sur un 404.
- Les liens entrants depuis la vitrine ou des canaux externes doivent
  être audités.

**Verdict** : **Conforme partiellement.** Correction nécessaire avant
ouverture grand public — voir [F-02](#7-tableau-des-findings-classés-par-sévérité).

---

### 5.3 Console d'administration

**`https://admin.gathe-finance.horus-lab.com/`** — *Plateforme la plus dégradée.*

| Paramètre | Valeur observée |
|---|---|
| Code HTTP `/` | `200 OK` (avec redirection interne vers `/dashboard`) |
| Code HTTP `/dashboard` | `200 OK` mais **contenu = "Chargement…" infini** |
| Code HTTP `/login` | `200 OK` — formulaire complet rendu |
| Code HTTP `/fr` | `404` (pas d'i18n côté admin) |
| Titre HTML | `Gathe Finance · Administration` |

**Constats détaillés**

- 🟢 **La page `/login` rend correctement** :
  - Titre "Gathe Finance · Administration"
  - Sous-titre "Réservé au personnel de la coopérative"
  - Champs "Adresse e-mail", "Mot de passe"
  - Bouton "Se connecter"
  - Lien sortant "Tu cherches l'espace membre ?"
- 🔴 **La racine `/` redirige vers `/dashboard`**, qui dépend du layout
  `(authed)`. Sans cookie de session valide, le composant client appelle
  `/api/v1/members/me/` qui répond `403`, et **l'application reste figée
  en état *"Chargement…"* sans aucune redirection vers `/login`**.
- 🔴 La conséquence est qu'un opérateur staff qui tape directement
  `admin.gathe-finance.horus-lab.com` dans la barre d'adresse voit un
  écran de chargement éternel — son seul recours est de **deviner
  l'URL `/login`**.

**Origine de l'anomalie**

Le middleware Next.js (`apps/admin/src/middleware.ts`) ne couvre vraisemblablement
pas le cas `cookie absent → redirection vers /login`, ou la garde côté
composant ne déclenche pas `router.push("/login")` lorsque `members/me`
retourne 403.

**Impact métier**

Bloquant pour la prise en main par l'équipe staff. Cette friction sera
perçue comme un bug applicatif majeur lors de la formation des opérateurs.

**Verdict** : **Non conforme.** Voir [F-01](#7-tableau-des-findings-classés-par-sévérité).

---

### 5.4 API REST

**`https://api.gathe-finance.horus-lab.com`**

| Endpoint | Méthode | Code | Statut |
|---|---|---|---|
| `/healthz/` | GET | `200` | 🟢 healthy probe OK |
| `/api/v1/savings/info/` | GET | `200` | 🟢 payload JSON conforme |
| `/api/v1/auth/login/` | POST | `400` | 🟢 (mauvais payload → message FR correct) |
| `/api/v1/auth/login/` | GET | `405` | 🟢 method not allowed attendu |
| `/api/v1/members/me/` | GET (anon) | `403` | 🟢 auth requise |

**Constats**

- 🟢 Le backend Django répond rapidement, accepte les requêtes POST,
  retourne des messages d'erreur en français (`"Email et mot de passe requis."`).
- 🟢 L'endpoint public `/api/v1/savings/info/` renvoie un payload JSON
  conforme aux règles métier 2026 (montant suggéré 1 000 XAF, cut-off
  17h, canal Tara primaire).
- 🟢 Le conteneur `gathe-finance-prod-backend-1` est marqué *(healthy)*
  par Docker.
- 🟢 La base Postgres a été réinitialisée proprement après reset du
  mot de passe, le volume `db_data` accueille un schéma migré complet.

**Verdict** : **Conforme**. Production-ready.

---

### 5.5 CMS Wagtail

**`https://cms.gathe-finance.horus-lab.com`**

| Endpoint | Code | Statut |
|---|---|---|
| `/` | `302 → vitrine` | 🟠 Comportement inattendu |
| `/admin/` | `200` (titre *S'identifier - Wagtail*) | 🟢 console accessible |
| `/api/v2/pages/` | `200` | 🟢 API headless OK |
| `/cms/admin/` | `404` | 🟢 normal (path inutile) |

**Constats**

- 🟢 La console Wagtail répond correctement sous `/admin/`, le formulaire
  d'authentification s'affiche, et l'API headless `/api/v2/pages/` est
  exploitable par les fronts Next.js et mobile.
- 🟠 La **racine `cms.gathe-finance.horus-lab.com/` redirige
  silencieusement vers la vitrine publique**. C'est dû au fait que le
  même conteneur Django sert le routage Wagtail à `""` et que la
  homepage Wagtail est aussi celle de la vitrine. Aucun message
  contrôlé n'est servi à un utilisateur curieux.
- 🔎 Cela n'est pas dangereux mais c'est **un signal de déploiement
  non finalisé**. Un opérateur découvrant l'URL devrait voir une page
  "Console d'édition — `/admin/`" ou être directement redirigé vers
  `/admin/`.

**Verdict** : **Conforme partiellement.** Voir [F-03](#7-tableau-des-findings-classés-par-sévérité).

---

### 5.6 Application mobile Flutter

**Build local effectué le 23 juin 2026 — résultats**

| Indicateur | Résultat |
|---|---|
| `flutter pub get` | ✅ succès |
| `flutter analyze` | 62 infos/warnings (tolérés), 0 erreur fatale |
| `flutter test` | **118 / 118 verts** |
| Build AAB release | ✅ `app-release.aab` 53,7 Mo |
| Signature | gathefinance-upload.jks valide |
| `API_BASE_URL` gravé | `https://api.gathe-finance.horus-lab.com` |

**Constats**

- 🟢 La configuration `ApiConfig.baseUrl` est injectable via
  `--dart-define` à la compilation, sans modification de source.
- 🟢 Le binaire AAB est prêt pour upload sur la console Google Play.
  Le SHA-256 est consigné dans le bordereau de livraison.
- 🟢 La suite de tests couvre l'auth, l'épargne, le crédit, les
  paiements, les notifications, le profil, l'onboarding et le PIN.
- ⚠️ Les **62 issues d'analyse statique** sont des `unawaited_futures`,
  des `trailing_commas` manquantes et un `unused_import`. Aucune n'est
  bloquante mais un *sweep* dédié serait sain.

**Verdict** : **Conforme et livrable.**

---

## 6. Infrastructure et exploitation

### 6.1 Hôte

- **Fournisseur** : Contabo
- **IP publique** : `81.0.246.144`
- **OS** : Ubuntu 24.04.4 LTS
- **Kernel** : `6.8.0-106-generic`
- **Charge moyenne** : 0,32 (sain)
- **Disque** : 51,7 % utilisé sur 95,82 Go (sain)
- **RAM** : 49 % utilisée

### 6.2 Reverse-proxy mutualisé

Le conteneur `backend-nginx-1` (image `nginx:alpine`) sert simultanément
**quatre projets indépendants** :

| Projet | Sous-domaines | Cohabitation |
|---|---|---|
| afrikamode | `backend.afrikamode.horus-lab.com` | 🟢 OK |
| ~~assistant-direction-api~~ | ~~`api-assistant-ia.horus-lab.com`~~ | 🟡 **Bloc retiré** durant l'audit (cf. §6.3) |
| edlearning | `edlearning.horus-lab.com` | 🟢 OK |
| **Gathe Finance** | 5 sous-domaines listés en §3.1 | 🟢 OK |

L'orchestration s'appuie sur le compose override `docker-compose.nginx-external.yml`
qui pose les alias DNS internes `gathe-backend`, `gathe-db`, `gathe-site`,
`gathe-portal`, `gathe-admin` sur le réseau partagé `backend_default`.

### 6.3 Incident corrigé en cours d'audit

Lors de la mise en route, le redémarrage de `backend-nginx-1` échouait
avec l'erreur :

```
[emerg] host not found in upstream "assistant-direction-api"
in /etc/nginx/conf.d/default.conf:182
```

Le conteneur `assistant-direction-api` (projet tiers) avait été retiré
du serveur sans nettoyage de la configuration nginx, ce qui bloquait
la résolution DNS au démarrage du proxy et **mettait au sol l'ensemble
des quatre projets** mutualisés.

**Action de remédiation appliquée** : suppression des lignes 140-199
de `/home/deploy/afrikamode/backend/deploy/nginx/default.conf` (deux
server blocks `api-assistant-ia`), backup créé en `.bak`, restart
`backend-nginx-1` validé.

### 6.4 Pipeline CI/CD

Deux workflows GitHub Actions sont armés :

- **`ci.yml`** — Tests obligatoires (`ruff` + `pytest` backend, `npm lint`
  + `tsc` frontend, `flutter analyze` + `flutter test`) puis build
  parallèle de 4 images GHCR (`backend`, `site`, `portal`, `admin`).
- **`deploy.yml`** — Déclenché sur succès de CI, SSH au VPS, `docker
  compose pull && up -d`, attente healthcheck backend, rollback
  automatique sur l'ancien tag d'image en cas d'échec, smoke tests
  des 5 endpoints publics depuis le runner GitHub.

⚠️ **Le déploiement automatique n'est pas encore actif** car les trois
secrets GitHub (`VPS_HOST`, `VPS_USER`, `VPS_SSH_PRIVATE_KEY`) n'ont pas
été posés. C'est intentionnel — l'exploitant souhaite valider le
premier déploiement manuel avant d'activer l'automatisation.

### 6.5 Sauvegardes

- **Postgres** : `pg_dump` cron quotidien à 03h00 UTC vers le volume
  `gathe-finance-prod_backups`.
- **Rétention** : 30 jours (`BACKUP_RETENTION_DAYS=30`).
- ⚠️ **Pas de réplication hors-VPS** à ce stade. Recommandation : pousser
  les dumps vers un stockage tiers (Backblaze B2, OVH PCA) via `rsync`
  hebdomadaire.

---

## 7. Tableau des findings classés par sévérité

### Légende

| Sévérité | Définition | Délai de remédiation attendu |
|---|---|---|
| 🔴 **CRITIQUE** | Blocage métier / sécurité / pertes de données | < 24 h |
| 🟠 **MAJEUR** | Friction UX significative, contournable mais visible | < 7 jours |
| 🟡 **MINEUR** | Anomalie cosmétique ou ergonomique non bloquante | < 30 jours |
| 🔵 **INFO** | Recommandation d'optimisation | Planifié |

### Liste

| ID | Sévérité | Composant | Constat | Détail |
|---|---|---|---|---|
| **F-01** | 🟠 MAJEUR | Console admin | `/` reste en *"Chargement…"* infini sans redirection vers `/login` | [§5.3](#53-console-dadministration) |
| **F-02** | 🟠 MAJEUR | Portail membre | Routes non préfixées (`/login`, `/dashboard`) retournent 404, devraient rediriger vers `/<locale>/...` | [§5.2](#52-portail-membre) |
| **F-03** | 🟡 MINEUR | CMS Wagtail | Racine `cms.*/` redirige vers la vitrine au lieu d'une page contrôlée | [§5.5](#55-cms-wagtail) |
| **F-04** | 🟡 MINEUR | Mobile | 62 infos/warnings d'analyse statique (`unawaited_futures`, `prefer_const_constructors`) | [§5.6](#56-application-mobile-flutter) |
| **F-05** | 🔵 INFO | Backups | Aucune réplication hors-VPS — risque corruption / ransomware | [§6.5](#65-sauvegardes) |
| **F-06** | 🔵 INFO | CI/CD | Secrets GitHub pas encore posés → CD auto inactif | [§6.4](#64-pipeline-cicd) |
| **F-07** | 🔵 INFO | Tara MoMo | Webhook URL pas encore déclarée dans le dashboard Tara | §8 |
| **F-08** | 🔵 INFO | Brevo | Domaine expéditeur `horus-lab.com` à vérifier dans Brevo | §8 |

### Aucun finding 🔴 critique

À la date du présent rapport, **l'audit n'a identifié aucun blocage
sécuritaire ou perte de données imminente**. Les corrections sont
exclusivement liées à l'UX et à des actions d'exploitation à finaliser.

---

## 8. Recommandations priorisées

### Court terme (7 jours)

1. **Corriger F-01 — Admin loading gate**
   Ajouter un middleware Next.js qui redirige `/(authed)/*` vers `/login`
   quand la session est absente, plutôt que de laisser le composant
   client tenter un fetch authentifié qui échoue silencieusement.

2. **Corriger F-02 — Portail routes non préfixées**
   Implémenter un fallback `next-intl` côté middleware qui détecte les
   chemins sans préfixe et les redirige vers `/<defaultLocale>/<path>`.

3. **Corriger F-03 — Wagtail racine `cms.*/`**
   Ajouter une redirection nginx ou un Wagtail page rule pour servir
   un message d'orientation `/admin/` sur le sous-domaine cms.*.

### Moyen terme (30 jours)

4. **F-04 — Cleanup analyse statique mobile**
   Sweep dédié `unawaited_futures` + `trailing_commas` + suppression
   imports inutilisés. Durcir le `analysis_options.yaml` ensuite pour
   prévenir les régressions.

5. **F-05 — Réplication backups hors-VPS**
   Script cron quotidien `rsync` vers un bucket Backblaze B2 chiffré.

6. **F-06 — Activer le CD auto**
   Poser les trois secrets GitHub (`VPS_HOST`, `VPS_USER`,
   `VPS_SSH_PRIVATE_KEY`) après avoir validé manuellement que le
   premier déploiement automatique fonctionne sur un commit factice.

### Exploitation (à faire dès aujourd'hui)

7. **F-07 — Déclarer le webhook Tara**
   Dans le dashboard `taramoney.com` :
   ```
   URL    : https://api.gathe-finance.horus-lab.com/api/v1/payments/webhook/tara/
   Secret : TARA_WEBHOOK_SECRET du .env.prod
   ```

8. **F-08 — Vérifier le sender Brevo**
   Console Brevo > *Senders, Domains & dedicated IPs* > vérifier que
   `horus-lab.com` est marqué *Verified*. Sinon, ajouter SPF + DKIM
   + DMARC chez le registrar.

9. **Publier l'AAB sur Play Console**
   Upload manuel de `mobile/build/app/outputs/bundle/release/app-release.aab`
   sur https://play.google.com/console — premier examen Google ~48-72 h.

---

## 9. Annexes

### 9.1 Tableau récapitulatif des codes HTTP observés

| URL | Méthode | Code | Taille | Titre |
|---|---|---|---|---|
| `gathe-finance.horus-lab.com/` | GET | 200 | 197 942 | Gathe Finance — Coopérative… |
| `portail.gathe-finance.horus-lab.com/` | GET | 200 | 10 373 | Gathe Finance · Espace membre |
| `portail.gathe-finance.horus-lab.com/fr` | GET | 200 | 10 373 | Gathe Finance · Espace membre |
| `portail.gathe-finance.horus-lab.com/login` | GET | 404 | 7 383 | (notFound) |
| `admin.gathe-finance.horus-lab.com/` | GET | 200 | 8 797 | Gathe Finance · Administration |
| `admin.gathe-finance.horus-lab.com/login` | GET | 200 | 9 022 | Gathe Finance · Administration |
| `admin.gathe-finance.horus-lab.com/dashboard` | GET | 200 | 8 797 | (Chargement…) |
| `admin.gathe-finance.horus-lab.com/fr` | GET | 404 | 7 100 | (notFound) |
| `api.gathe-finance.horus-lab.com/healthz/` | GET | 200 | 16 | (OK) |
| `api.gathe-finance.horus-lab.com/api/v1/savings/info/` | GET | 200 | 695 | (JSON) |
| `api.gathe-finance.horus-lab.com/api/v1/auth/login/` | POST | 400 | — | (Email et mot de passe requis.) |
| `cms.gathe-finance.horus-lab.com/` | GET | 302→vitrine | 0 | (redirect) |
| `cms.gathe-finance.horus-lab.com/admin/` | GET | 200 | 12 614 | S'identifier - Wagtail |
| `cms.gathe-finance.horus-lab.com/api/v2/pages/` | GET | 200 | 3 901 | (JSON Wagtail) |

### 9.2 Inventaire des conteneurs en production

| Container | Image | Statut |
|---|---|---|
| `gathe-finance-prod-db-1` | postgres:16-alpine | Up (healthy) |
| `gathe-finance-prod-backend-1` | ghcr.io/.../backend:latest | Up (healthy) |
| `gathe-finance-prod-qcluster-1` | ghcr.io/.../backend:latest | Up |
| `gathe-finance-prod-site-1` | ghcr.io/.../site:latest | Up |
| `gathe-finance-prod-portal-1` | ghcr.io/.../portal:latest | Up |
| `gathe-finance-prod-admin-1` | ghcr.io/.../admin:latest | Up |
| `gathe-finance-prod-backup-1` | postgres:16-alpine | Up |
| `backend-nginx-1` (mutualisé) | nginx:alpine | Up |

### 9.3 Documents de référence

- `audit/AUDIT_2026-06-20.md` — Audit sécurité et règles métier (du 20 juin 2026)
- `audit/TESTS_PLAN.md` — Plan de tests recette utilisateur
- `audit/PLAY_STORE.md` — Checklist publication Google Play
- `infra/DEPLOYMENT.md` — Guide de déploiement A→Z (701 lignes)
- `architecture/BUSINESS_RULES_2026.md` — Source de vérité règles métier

### 9.4 Bordereau de livraison mobile

| Élément | Valeur |
|---|---|
| Fichier | `mobile/build/app/outputs/bundle/release/app-release.aab` |
| Taille | 53,7 Mo |
| SHA-256 | `b329b3e7ab7689ef96eb7bb27aa4c10b97eefb0cbdc8003596ea54edceb90514` |
| Keystore | `mobile/android/keystore/gathefinance-upload.jks` |
| `API_BASE_URL` | `https://api.gathe-finance.horus-lab.com` |

---

## Signature

> Rapport établi par le **Groupe Horus-lab** — Cellule Audit & Recette
> à Douala, le **23 juin 2026**.
>
> Le présent document a valeur de constat à date.
> Les corrections recommandées en §8 feront l'objet d'un rapport
> complémentaire **« Plan de remédiation »** une fois les actions
> exécutées et re-contrôlées.

```
                                ⚖
                          Horus-lab
                   Cellule Audit & Recette
                      Douala — Cameroun
```

*Fin du rapport.*
