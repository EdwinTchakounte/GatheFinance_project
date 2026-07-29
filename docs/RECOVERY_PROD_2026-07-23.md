# 🚑 Recovery prod — backend cassé le 2026-07-23

## Ce qui s'est passé
Sur le serveur (`/opt/gathe-finance`), la commande
`docker compose -f infra/docker-compose.prod.yml up -d --build backend qcluster`
a été lancée **sans `--env-file`** → toutes les variables d'env étaient vides
(`POSTGRES_*`, `DJANGO_SECRET_KEY`, domaines…) → le backend recréé plante :

```
django.core.exceptions.ImproperlyConfigured: The SECRET_KEY setting must not be empty.
→ Container gathe-finance-prod-backend-1 is restarting (unhealthy)
```

Le `git pull` a été **annulé** (modifs locales infra/nginx protégées) → le code
n'a pas changé. Le problème = l'environnement manquant + un `--build` inutile.

> ⚠️ Ce serveur (`/opt/gathe-finance`) se déploie avec `infra/docker-compose.prod.yml`
> **+ `--env-file`**, PAS par `git pull` + `--build`. Les images sont normalement
> pré-construites par la CI.

---

## 1. Trouver le fichier d'environnement

```bash
ls -la /opt/gathe-finance/infra/.env.prod /opt/gathe-finance/.env.prod 2>/dev/null
```

---

## 2. Relancer AVEC l'env + LES 2 COMPOSE (et SANS `--build`)

⚠️ Ce serveur est derrière le **nginx partagé** (afrikamode) : il FAUT le second
fichier `docker-compose.nginx-external.yml`, sinon les services ne sont pas
rattachés au réseau partagé (alias `gathe-backend`/`gathe-site`/…) → **502**.

```bash
cd /opt/gathe-finance
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod up -d
```

*(Si l'env est à la racine du dossier et non dans `infra/`, remplacer
`infra/.env.prod` par `.env.prod`.)*

> C'est la commande de déploiement de référence de CE serveur : **2 compose
> (`prod` + `nginx-external`) + `--env-file`**, jamais Traefik seul, jamais `--build`.

---

## 3. Vérifier le rétablissement

```bash
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod ps
curl -s -o /dev/null -w "backend %{http_code}\n" https://api.gathe-finance.horus-lab.com/healthz/
curl -s -o /dev/null -w "api     %{http_code}\n" https://api.gathe-finance.horus-lab.com/api/v1/auth/csrf/
```

Attendu : backend **healthy** + **200** sur les deux `curl`.

> Si le backend est `healthy` mais que le `curl` renvoie **502** : c'est l'oubli
> du `-f infra/docker-compose.nginx-external.yml` (services hors réseau partagé).
> Relancer l'étape 2 avec les 2 compose. Dépannage immédiat de l'alias :
> ```bash
> docker network connect --alias gathe-backend backend_default gathe-finance-prod-backend-1
> docker exec backend-nginx-1 nginx -s reload
> ```

---

## 4. (Après rétablissement) Remettre la bonne image #43 si régression

Le `--build` a reconstruit le backend depuis le code LOCAL (commit antérieur à la
PR #43). Pour revenir à l'image CI correcte :

```bash
# Toujours les 2 compose, sinon le backend recréé perd son alias réseau → 502.
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod pull backend qcluster
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod up -d
```

*(Alternative : re-déclencher le workflow GitHub « Deploy to prod ».)*

---

## 5. NE PAS refaire pour l'instant
- ❌ `git pull` (casse les modifs locales infra/nginx du serveur).
- ❌ `--build` (reconstruit du code potentiellement plus ancien).
- ❌ Le reseed du schéma / `route_priority` **tant que le backend n'est pas
  healthy** — d'abord rétablir le service.

---

## À corriger ensuite (docs erronés)
Mes fichiers `docs/ACTIONS_PROD_2026-07-22.md` et `docs/COMMANDES_PROD_BRC_2026-07-23.md`
supposaient `git pull` + `--build` + `-f infra/...` **sans `--env-file`** → à
réécrire pour CE serveur : toujours `--env-file`, jamais `--build`, images via CI.
