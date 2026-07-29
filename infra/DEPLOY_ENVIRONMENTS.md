# Déploiement multi-environnements (staging = nous · production = client)

Objectif : **une même base de code, deux cibles de déploiement**, pilotées par la
branche Git et par les **GitHub Environments** (aucun secret dans le dépôt).

| Branche Git | GitHub Environment | Serveur                | Reverse-proxy        | Domaines            | Statut |
|-------------|--------------------|------------------------|----------------------|---------------------|--------|
| `staging`   | `staging`          | **notre** VPS Contabo  | nginx mutualisé (externe) | `*.horus-lab.com` | **ACTIF (phase 1)** |
| `main`      | `production`       | serveur **client** (dédié) | Traefik + Let's Encrypt | domaine client  | phase 2 (à venir) |

Flux visé : dev → merge dans **`staging`** → déploie **chez nous** (recette) →
merge `staging` → **`main`** → déploie **chez le client** (prod).

## Phase 1 (maintenant) — `main` INCHANGÉ, on branche seulement `staging`

- **`main` n'est pas modifié** : son `deploy.yml` d'origine continue de pointer
  sur notre Contabo (`production`), exactement comme avant.
- Le déploiement `staging` est **auto-contenu dans `ci.yml`** (job `deploy-staging`,
  gardé `if: branch == staging`). Il tourne depuis la branche `staging` elle-même,
  donc **rien à changer sur `main`**. Cf. `.github/workflows/ci.yml`.
- Phase 2 (serveur client sur `main` + Traefik) : on introduira alors un
  `deploy.yml` *environment-aware* + l'Environment `production` (client). Le
  template client est déjà prêt : `infra/.env.prod.client.example`.

> ⚠️ **Piège important** : les URLs publiques du front (`NEXT_PUBLIC_SITE_URL`,
> `NEXT_PUBLIC_PORTAL_URL`, `NEXT_PUBLIC_ADMIN`/`PORTAL`) sont **figées au build**
> de l'image Docker. Une image construite avec nos domaines ne peut donc pas
> servir les domaines du client. La CI construit donc **un jeu d'images par
> branche** : `:staging` (nos domaines) et `:main` (domaines client). Chaque
> serveur tire le tag de sa branche via `GATHE_IMAGE_TAG` dans son `.env.prod`.

---

## 1. Ce qui est piloté par la config (jamais commité)

### ⚠️ NOMS DISSOCIÉS recette (Contabo) vs client (Coolify)

Les secrets/variables sont **préfixés distinctement** pour éviter tout repli
croisé (ex. un `production` mal configuré retombant sur les secrets `VPS_*` de
Contabo → déploiement client sur le mauvais serveur). Règle :

- **`VPS_*` / `STAGING_*`** = notre recette Contabo (`horus-lab.com`), branche `staging`.
- **`CLIENT_*`** = serveur de la cliente sous Coolify (`gathe-finance.com`), branche `main`.

**Secrets** :

| Secret (recette)       | Secret (client)              | Rôle                                    |
|------------------------|------------------------------|-----------------------------------------|
| `VPS_HOST`             | `CLIENT_VPS_HOST`            | IP/hostname du serveur cible            |
| `VPS_USER`             | `CLIENT_VPS_USER`            | utilisateur SSH                         |
| `VPS_SSH_PRIVATE_KEY`  | `CLIENT_VPS_SSH_PRIVATE_KEY` | clé privée SSH dédiée déploiement       |
| `VPS_DEPLOY_PATH`      | `CLIENT_VPS_DEPLOY_PATH`     | (opt.) chemin repo — défaut `/opt/gathe-finance` |

**Variables** — non secrètes :

| Variable (recette)         | Variable (client)      | Valeur client                 |
|----------------------------|------------------------|-------------------------------|
| `STAGING_SITE_DOMAIN`      | `CLIENT_SITE_DOMAIN`   | `app.gathe-finance.com` *(vitrine sur app.)* |
| `STAGING_PORTAL_DOMAIN`    | `CLIENT_PORTAL_DOMAIN` | `portail.gathe-finance.com`   |
| `API_DOMAIN`               | `CLIENT_API_DOMAIN`    | `api.gathe-finance.com`       |
| `ADMIN_DOMAIN`             | `CLIENT_ADMIN_DOMAIN`  | `admin.gathe-finance.com`     |
| `CMS_DOMAIN`               | `CLIENT_CMS_DOMAIN`    | `cms.gathe-finance.com`       |

`CLIENT_SITE_DOMAIN` / `CLIENT_PORTAL_DOMAIN` servent aussi au **build** des
images `:main` (URLs Next figées) — cf. `ci.yml`. Les autres servent aux smoke
tests. Le **mode proxy** (Coolify) et le **certresolver** se règlent dans
`infra/.env.prod` SUR le serveur (`PROXY_NETWORK`, `TRAEFIK_CERTRESOLVER`), pas
en variables GitHub.

### Variables **de dépôt** (Settings → Variables) — pour le build d'images CI

La CI build les images du front avec les bons domaines selon la branche. Elles
retombent sur les domaines `horus-lab.com` si non définies (donc rien ne casse
avant configuration du client) :

| Variable de dépôt          | Valeur                          |
|----------------------------|---------------------------------|
| `STAGING_SITE_DOMAIN`      | `gathe-finance.horus-lab.com`   |
| `STAGING_PORTAL_DOMAIN`    | `portail.gathe-finance.horus-lab.com` |
| `STAGING_ADMIN_DOMAIN`     | `admin.gathe-finance.horus-lab.com` |
| `PROD_SITE_DOMAIN`         | domaine vitrine client          |
| `PROD_PORTAL_DOMAIN`       | domaine portail client          |
| `PROD_ADMIN_DOMAIN`        | domaine admin client            |

---

## 2. Sur le serveur CLIENT (dédié, Traefik) — bootstrap manuel (1 fois)

1. Installer Docker + docker compose plugin.
2. `git clone` le repo dans `/opt/gathe-finance` (ou `VPS_DEPLOY_PATH`).
3. `cp infra/.env.prod.client.example infra/.env.prod` puis **remplir tous les
   `__CHANGE_ME__`** (SECRET_KEY, Postgres, Brevo, domaines client, `ACME_EMAIL`,
   `GATHE_IMAGE_TAG=main`). Ce fichier reste **sur le serveur**, jamais commité.
4. `docker login ghcr.io` avec un PAT `read:packages` (accès aux images GHCR).
5. DNS : 5 enregistrements A (`racine`, `api.`, `portail.`, `admin.`, `cms.`)
   → IP du serveur client.
6. Premier démarrage : `docker compose -f infra/docker-compose.prod.yml --profile traefik --env-file infra/.env.prod up -d`
   (Traefik obtient les certificats Let's Encrypt automatiquement).
7. Seed initial : `docker compose ... exec backend python manage.py bootstrap_site && ... seed_blog && ... seed_email_templates --force && ... seed_fees && ... seed_rates && ... seed_q_schedules`.

Ensuite, chaque merge dans `main` déclenche CI (build `:main`) → deploy auto.

## 3. Clé SSH de déploiement (à faire par toi, jamais par l'assistant)

```bash
# Génère une paire DÉDIÉE au déploiement (ne réutilise pas ta clé perso) :
ssh-keygen -t ed25519 -C "gathe-deploy-client" -f ./gathe_deploy_client -N ""
# 1) Copie la clé PUBLIQUE sur le serveur client :
ssh-copy-id -i ./gathe_deploy_client.pub <VPS_USER>@<VPS_HOST>
# 2) Colle le contenu de ./gathe_deploy_client (la PRIVÉE) dans le secret GitHub
#    Environment `production` → VPS_SSH_PRIVATE_KEY
# 3) Supprime la copie locale de la clé privée après :
shred -u ./gathe_deploy_client
```

---

## 4. Infos serveur CLIENT à fournir (pour que je te dise exactement quoi saisir)

- [ ] IP / hostname du serveur client + utilisateur SSH (+ port si ≠ 22)
- [ ] Domaine racine client (j'en dérive api./portail./admin./cms.)
- [ ] `ACME_EMAIL` (email Let's Encrypt du client)
- [ ] Le client fournit-il ses propres secrets (Django SECRET_KEY, Postgres,
      Brevo API key, Tara) ou on les génère ?
- [ ] Un PAT GHCR `read:packages` disponible côté client (ou on réutilise le nôtre)

Les valeurs secrètes se saisissent **dans l'UI GitHub / sur le serveur**, jamais
dans le dépôt. Je ne manipule aucune clé privée ni mot de passe.
