# Diagnostic — `api.` et `cms.` renvoient 404 (après fix ALLOWED_HOSTS)

## État
- ✅ `ALLOWED_HOSTS` corrigé : `api.`/`cms.` sont passés de **400 → 404** (plus de DisallowedHost).
- ✅ `app.` / `portail.` / `admin.` → 200 · backend `healthy` · HTTPS OK.
- ❓ **404** sur `api.` et `cms.` (les deux tapent le backend Django).

Le 404 vient soit de **Django** (URL absente), soit de **Traefik** (ne route pas ces 2 domaines vers le backend). On discrimine ci-dessous.

---

## 🔎 Diagnostic

```bash
cd /home/gathe/gathe-finance/infra

# 1) le backend répond-il EN DIRECT (sans Traefik) ?
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend sh -lc 'curl -s -o /dev/null -w "backend direct /healthz/ -> %{http_code}\n" http://localhost:8000/healthz/'

# 2) les routeurs api./cms. sont-ils bien sur le conteneur backend ?
docker inspect gathe-finance-prod-backend-1 \
  -f '{{range $k,$v := .Config.Labels}}{{if (hasPrefix $k "traefik.")}}{{$k}}={{$v}}{{"\n"}}{{end}}{{end}}' \
  | grep -iE "gathe-api|gathe-cms|enable|docker.network|server.port"

# 3) re-tester en externe après ~30 s (Traefik met un instant à ré-enregistrer le backend recréé)
sleep 30
curl -s -o /dev/null -w "api  -> %{http_code}\n" https://api.gathe-finance.com/healthz/
curl -s -o /dev/null -w "cms  -> %{http_code}\n" https://cms.gathe-finance.com/admin/
```

---

## Interprétation & correctif

| Résultat | Cause | Correctif |
|---|---|---|
| (1)=200 **et** (3) reste 404 | app OK → **Traefik ne route pas** api./cms. | voir §A (routeurs/réseau) |
| (3)=200 après les 30 s | simple **délai** de ré-enregistrement Traefik | ✅ rien, c'est bon |
| (1)=404 | **Django** : URL /healthz/ absente dans l'image | voir §B (improbable) |

### §A — Traefik ne route pas api./cms.
Vérifier avec la sortie de (2) que le backend porte bien :
```
traefik.enable=true
traefik.http.routers.gathe-api.rule=Host(`api.gathe-finance.com`)
traefik.http.routers.gathe-cms.rule=Host(`cms.gathe-finance.com`)
traefik.http.routers.gathe-api.service=gathe-backend
traefik.http.services.gathe-backend.loadbalancer.server.port=8000
traefik.docker.network=<edge>
```
- Si ces labels **manquent** → le backend a été recréé sans l'override client. Recréer proprement :
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  up -d --no-deps --force-recreate backend
```
- Si les labels **sont là** mais 404 persiste → `traefik.docker.network` ne pointe pas sur le bon réseau, ou le backend n'est pas sur le réseau `edge` de Traefik :
```bash
docker inspect gathe-finance-prod-backend-1 \
  -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
#   doit contenir le réseau EDGE (celui du Traefik)
grep -E "^EDGE_NETWORK=" .env.prod    # doit = le vrai réseau de Traefik
```
Puis recréer le backend.

### §B — Django renvoie 404 (si (1)=404)
Peu probable (horus-lab répond 200 sur /healthz/). Vérifier l'URL exacte / la santé applicative :
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend python manage.py showmigrations | head
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend sh -lc 'curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/admin/'
```

---

## Note — `cms.` renvoie normalement 302 (pas 200)
`cms.gathe-finance.com/admin/` redirige vers la page de login Wagtail → **302** attendu (pas 200). Un `curl -sI` le montre :
```bash
curl -sI https://cms.gathe-finance.com/admin/ | grep -iE "HTTP/|location"
```

---

## ▶️ Ensuite
Coller les sorties **(1) (2) (3)** → correctif ciblé → puis :
```bash
gh workflow run deploy.yml -f image_tag=main    # run tout vert
# post-déploiement (seeds) :
bash /home/gathe/gathe-finance/infra/scripts/post-deploy-seed.sh
```

## Rappel — progression
| Étape | État |
|---|---|
| SSH · user · upload · `.env.prod` · GHCR · pull · conteneurs · DB · backend healthy | ✅ |
| `app.`/`portail.`/`admin.` en ligne | ✅ |
| ALLOWED_HOSTS (plus de 400) | ✅ |
| **routage api./cms.** | 🔧 ce document |
| redirection apex → app (bascule DNS) | 🧰 préparé (autre doc) |
