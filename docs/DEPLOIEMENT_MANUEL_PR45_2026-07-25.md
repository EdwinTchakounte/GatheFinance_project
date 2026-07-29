# Déploiement manuel PR #45 — CI GitHub gelée (billing)

> **Contexte** : GitHub Actions est bloqué (paiement) → ni build d'images, ni
> auto-deploy. On reproduit **à la main** ce que fait le pipeline :
> build 4 images → push ghcr → `pull` + `up -d` sur le VPS.
>
> **Règle d'or VPS** (cf. `DEPLOIEMENT_SERVEUR_GATHE.md`) : toujours **les 2 compose**
> + `--env-file infra/.env.prod`, **jamais** `--build`, **jamais** `git pull`.

Toutes les commandes `docker build/push` se lancent **depuis la racine du repo**
(`/home/tchakounte/Desktop/Gathe_finance`).

---

## 0. Variables communes

```bash
cd /home/tchakounte/Desktop/Gathe_finance

IMAGE_BASE=ghcr.io/edwintchakounte/gathefinance_project
PLATFORM=linux/amd64            # le VPS Contabo est x86_64

# VPS
VPS=root@81.0.246.144           # vmi3289409
KEY=~/.ssh/gathe_ci
DC="docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod"
```

---

## 1. Login ghcr — DÉJÀ FAIT ✅

Vérifié le 2026-07-25 : session ghcr valide (user `EdwinTchakounte`), les 4 images
`:latest` (backend/site/portal/admin) sont lisibles. **Rien à faire ici.**

Re-vérifier au besoin :

```bash
for i in backend site portal admin; do
  docker manifest inspect $IMAGE_BASE/$i:latest >/dev/null && echo "$i ✅" || echo "$i KO"
done
```

> Si un jour ça repasse en 401/403 : `docker login ghcr.io -u EdwinTchakounte`
> (PAT avec scope `write:packages`).

---

## 2. Build des 4 images (mêmes contextes/targets/args que `ci.yml`)

### 2.1 Backend
```bash
docker build \
  --platform $PLATFORM \
  --target prod \
  -t $IMAGE_BASE/backend:latest \
  backend
```

### 2.2 Site (vitrine)
```bash
docker build \
  --platform $PLATFORM \
  --target runner-site \
  --build-arg CMS_API_URL=http://backend:8000 \
  --build-arg NEXT_PUBLIC_SITE_URL=https://gathe-finance.horus-lab.com \
  --build-arg NEXT_PUBLIC_PORTAL_URL=https://portail.gathe-finance.horus-lab.com \
  -t $IMAGE_BASE/site:latest \
  frontend
```

### 2.3 Portail
```bash
docker build \
  --platform $PLATFORM \
  --target runner-portal \
  --build-arg BACKEND_INTERNAL_URL=http://backend:8000 \
  --build-arg NEXT_PUBLIC_SITE_URL=https://gathe-finance.horus-lab.com \
  -t $IMAGE_BASE/portal:latest \
  frontend
```

### 2.4 Admin
```bash
docker build \
  --platform $PLATFORM \
  --target runner-admin \
  --build-arg BACKEND_INTERNAL_URL=http://backend:8000 \
  --build-arg NEXT_PUBLIC_PORTAL_URL=https://portail.gathe-finance.horus-lab.com \
  -t $IMAGE_BASE/admin:latest \
  frontend
```

---

## 3. Push des 4 images sur ghcr

```bash
docker push $IMAGE_BASE/backend:latest
docker push $IMAGE_BASE/site:latest
docker push $IMAGE_BASE/portal:latest
docker push $IMAGE_BASE/admin:latest
```

---

## 4. Déploiement sur le VPS

Le VPS tire les nouvelles images `latest` et recrée les conteneurs.

```bash
ssh -i $KEY $VPS 'bash -s' <<'REMOTE'
set -euo pipefail
cd /opt/gathe-finance
DC="docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod"

echo ">>> Pull des nouvelles images..."
$DC pull backend qcluster site portal admin

echo ">>> Redémarrage des services..."
$DC up -d

echo ">>> Attente backend healthy..."
for i in $(seq 1 18); do
  STATUS=$($DC ps --format json backend 2>/dev/null | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
  echo "  $i/18 : backend=$STATUS"
  [ "$STATUS" = "healthy" ] && break
  sleep 5
done

echo ">>> Migrations Django..."
$DC exec -T backend python manage.py migrate --noinput

echo ">>> Reload nginx partagé..."
docker restart backend-nginx-1 || true

echo ">>> État final :"
$DC ps
REMOTE
```

> **Note migrations PR #45** : `audit/0005_blockedip` (table BlockedIP) +
> `loans/…` (si migration ajoutée). `migrate` au boot les applique ; la ligne
> explicite ci-dessus est une ceinture-bretelle.

---

## 5. Smoke tests (depuis la machine locale)

```bash
for url in \
  https://api.gathe-finance.horus-lab.com/healthz/ \
  https://gathe-finance.horus-lab.com/ \
  https://portail.gathe-finance.horus-lab.com/ \
  https://admin.gathe-finance.horus-lab.com/ \
  https://cms.gathe-finance.horus-lab.com/admin/
do
  code=$(curl -sLo /dev/null -w "%{http_code}" --max-time 15 "$url" || echo "000")
  echo "$code  $url"
done
```
Attendu : **2xx / 3xx** partout.

---

## 6. Rollback (si un endpoint tombe)

Les images précédentes existent encore sur ghcr sous leur tag `sha-XXXX`.
Le plus simple si on n'a pas noté le sha : re-tag l'ancienne image locale, ou
pinner un tag connu dans `.env.prod` (`GATHE_IMAGE_TAG=sha-XXXX`) puis `$DC up -d`.

Dépannage 502 (backend healthy mais API KO = alias réseau perdu) :
```bash
ssh -i $KEY $VPS 'docker network connect --alias gathe-backend backend_default gathe-finance-prod-backend-1; docker exec backend-nginx-1 nginx -s reload'
```

---

## 7. Après déploiement OK — aligner `main`

```bash
# Merge PR #45 pour que main = ce qui tourne en prod
gh pr merge 45 --merge --admin
```

---

## Plan B — sans ghcr (si pas de PAT `write:packages`)

Build local → transfert direct → load sur le VPS (aucun push ghcr) :

```bash
# 1. Build (étape 2 ci-dessus, identique)
# 2. Save + transfert + load
for img in backend site portal admin; do
  docker save $IMAGE_BASE/$img:latest | gzip | \
    ssh -i $KEY $VPS "gunzip | docker load"
done
# 3. up -d SANS pull (utilise les images chargées localement sur le VPS)
ssh -i $KEY $VPS 'cd /opt/gathe-finance && docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod up -d'
```
Plus lent (transfert des layers via SSH) mais ne nécessite aucun token ghcr.
