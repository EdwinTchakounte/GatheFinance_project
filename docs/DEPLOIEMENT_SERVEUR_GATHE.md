# Déploiement / ops prod GATHE — RÈGLE D'OR

Serveur : `/opt/gathe-finance` (root@vmi3289409). Conteneurs `gathe-finance-prod-*`,
derrière le **nginx partagé** (afrikamode). Images pré-construites par la CI
(ghcr, tag `latest`).

---

## ⭐ La règle d'or

**TOUTE** commande `docker compose … up` sur ce serveur DOIT :
- inclure **LES 2 fichiers compose** :
  `-f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml`
- passer **`--env-file infra/.env.prod`**
- **JAMAIS `--build`** (les images viennent de la CI)
- **JAMAIS `git pull`** (des modifs locales infra/nginx sont protégées sur le serveur)

> Pourquoi les 2 compose : `nginx-external.yml` rattache les services au réseau
> partagé `backend_default` avec les alias `gathe-backend` / `gathe-site` /
> `gathe-portal` / `gathe-admin`. **Sans lui, le backend recréé perd son alias
> → l'API renvoie 502.** Sans `--env-file`, `SECRET_KEY` est vide → le backend
> crash-loop.

Alias pratique (à définir une fois par session SSH) :
```bash
cd /opt/gathe-finance
DC="docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod"
```

---

## Commandes courantes

**(Re)démarrer / redéployer tous les services :**
```bash
$DC up -d
```

**Récupérer la dernière image CI puis redéployer :**
```bash
$DC pull backend qcluster
$DC up -d
```

**Lancer une commande de gestion Django (migrate, seed, shell…) :**
```bash
$DC exec backend python manage.py <commande>
```

**État + logs :**
```bash
$DC ps
$DC logs -f backend
```

**Vérifier l'API depuis n'importe où :**
```bash
curl -s -o /dev/null -w "healthz %{http_code}\n" https://api.gathe-finance.horus-lab.com/healthz/
curl -s -o /dev/null -w "csrf    %{http_code}\n" https://api.gathe-finance.horus-lab.com/api/v1/auth/csrf/
```
Attendu : **200 / 200**.

---

## Si l'API renvoie 502 alors que le backend est `healthy`

Le backend a été recréé sans le réseau partagé (compose unique). Deux options :

1. **Propre** — relancer avec les 2 compose : `$DC up -d`.
2. **Dépannage immédiat** — reconnecter l'alias + reload nginx :
```bash
docker network connect --alias gathe-backend backend_default gathe-finance-prod-backend-1
docker exec backend-nginx-1 nginx -s reload
```

---

## À NE JAMAIS faire sur ce serveur
- ❌ `docker compose … up` avec **un seul** fichier compose.
- ❌ `--build`.
- ❌ `git pull` (utiliser les images CI ; ne pas écraser les modifs locales infra/nginx).
- ❌ Une commande de mon doc `ACTIONS_PROD_2026-07-22.md` / `COMMANDES_PROD_BRC_2026-07-23.md`
  telle quelle (elles supposaient `git pull` + `--build` + 1 seul compose sans env).
  → Toujours transposer avec le `$DC` ci-dessus.
