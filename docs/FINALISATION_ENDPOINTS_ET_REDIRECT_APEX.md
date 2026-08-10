# Finalisation — endpoints backend (400) + redirection gathe-finance.com → app.

## État
Déploiement cliente quasi complet : backend `healthy`, certificats HTTPS OK.
- ✅ `app.` / `portail.` / `admin.` → 200
- ✗ `api.` / `cms.` → **400** (les deux tapent le backend Django)

---

# Partie 1 — Corriger `api.` et `cms.` (400 = DisallowedHost) — À FAIRE MAINTENANT

Un **400** sur un domaine Django = le domaine n'est pas dans `DJANGO_ALLOWED_HOSTS`.

```bash
cd /home/gathe/gathe-finance/infra

# 1) voir la valeur actuelle
grep -E "^DJANGO_ALLOWED_HOSTS=" .env.prod

# 2) forcer les 5 domaines (dont api. et cms.)
sed -i 's#^DJANGO_ALLOWED_HOSTS=.*#DJANGO_ALLOWED_HOSTS=app.gathe-finance.com,portail.gathe-finance.com,admin.gathe-finance.com,api.gathe-finance.com,cms.gathe-finance.com#' .env.prod

# 3) (pour la connexion admin/CMS ensuite) CSRF + CORS
sed -i 's#^CSRF_TRUSTED_ORIGINS=.*#CSRF_TRUSTED_ORIGINS=https://admin.gathe-finance.com,https://cms.gathe-finance.com,https://portail.gathe-finance.com#' .env.prod
sed -i 's#^CORS_ALLOWED_ORIGINS=.*#CORS_ALLOWED_ORIGINS=https://app.gathe-finance.com,https://portail.gathe-finance.com,https://admin.gathe-finance.com#' .env.prod

# 4) recréer le backend pour prendre les nouvelles variables
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod up -d --no-deps --force-recreate backend
sleep 12

# 5) vérifier
curl -s -o /dev/null -w "api  -> %{http_code}\n" https://api.gathe-finance.com/healthz/
curl -s -o /dev/null -w "cms  -> %{http_code}\n" https://cms.gathe-finance.com/admin/
```
→ attendu : `api -> 200`, `cms -> 302` (redirection login = normal).

---

# Partie 2 — Servir la vitrine sur `gathe-finance.com` + `www` (même contenu que `app.`)

But : `gathe-finance.com`, `www.gathe-finance.com` **et** `app.gathe-finance.com` affichent **tous** la vitrine, **sans redirection** (même service `gathe-site`).

> ✅ **Déjà fait dans le code** (`infra/docker-compose.client.yml`, commit sur `main`) : un router `gathe-apex` pointe sur le service `gathe-site`. Il ne reste que le DNS (2.1) + un déploiement (2.3).

## 2.1 DNS (chez le registrar) — au moment de la bascule
Ajouter des enregistrements **A** vers l'IP du serveur (`169.58.69.78`) :
```
gathe-finance.com.        A   169.58.69.78
www.gathe-finance.com.    A   169.58.69.78
```
> Indispensable AVANT que Traefik puisse émettre les certificats pour l'apex + www (challenge ACME).

## 2.2 Ce qui est déjà en place (rappel du code)
Dans `infra/docker-compose.client.yml`, service `site` :
```yaml
      - "traefik.http.routers.gathe-apex.rule=Host(`gathe-finance.com`) || Host(`www.gathe-finance.com`)"
      - "traefik.http.routers.gathe-apex.entrypoints=${TRAEFIK_ENTRYPOINT:-websecure}"
      - "traefik.http.routers.gathe-apex.tls=true"
      - "traefik.http.routers.gathe-apex.tls.certresolver=${TRAEFIK_CERTRESOLVER:-letsencrypt}"
      - "traefik.http.routers.gathe-apex.service=gathe-site"   # même service que app. -> même contenu
```

## 2.3 Appliquer
- **Via la CI** (recommandé) : `gh workflow run deploy.yml -f image_tag=main` (le compose à jour est renvoyé au serveur + `up`).
- **Direct serveur** (test rapide, après `git pull` ou re-scp du compose) :
```bash
cd /home/gathe/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod up -d --no-deps --force-recreate site
```

## 2.4 Vérifier (une fois le DNS pointé)
```bash
curl -s -o /dev/null -w "apex -> %{http_code}\n" https://gathe-finance.com/
curl -s -o /dev/null -w "www  -> %{http_code}\n" https://www.gathe-finance.com/
#  attendu : 200 sur les deux (même vitrine que app.)
```

> ℹ️ La vitrine reste buildée avec `NEXT_PUBLIC_SITE_URL=app.gathe-finance.com` → le `canonical` SEO pointe sur `app.` (bon pour le référencement), même si le contenu s'affiche aussi sur l'apex.

---

## Rappel — progression
| Étape | État |
|---|---|
| SSH · user · upload · `.env.prod` · GHCR · pull · conteneurs · DB · backend `healthy` | ✅ |
| `app.`/`portail.`/`admin.` en ligne (HTTPS) | ✅ |
| **`api.`/`cms.` (ALLOWED_HOSTS)** | 🔧 Partie 1 |
| **redirection apex → app** (à la bascule DNS) | 🧰 Partie 2 (préparé) |
| post-déploiement (seeds) | à suivre |

> 🔐 Ne pas oublier : révoquer le PAT et changer le mot de passe DB affichés en clair pendant le debug.
