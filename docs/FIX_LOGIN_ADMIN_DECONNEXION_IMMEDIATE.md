# Fix — Login admin : « déconnexion immédiate » sur le serveur cliente

## Symptôme
Sur `https://admin.gathe-finance.com`, la connexion semble réussir puis renvoie
**aussitôt** à l'écran de login (boucle). Idem possible côté portail membre.

## Cause racine
L'authentification admin/portail est **par cookie de session** Django
(`credentials: include`, cookies `gathe_sessionid` + `csrftoken`).

Le domaine du cookie est piloté par `COOKIE_DOMAIN`. Or :

1. `config/settings/prod.py:94` a un **défaut codé en dur horus** :
   ```python
   _COOKIE_DOMAIN = env("COOKIE_DOMAIN", default=".gathe-finance.horus-lab.com")
   ```
2. **`infra/docker-compose.prod.yml` (ancre `x-backend-env`) ne transmettait PAS
   `COOKIE_DOMAIN`** au conteneur backend.

→ Sur la cliente, Django ignorait le `COOKIE_DOMAIN=.gathe-finance.com` du
`.env.prod` (jamais injecté) et posait le cookie avec
`Domain=.gathe-finance.horus-lab.com`. Le navigateur sur `admin.gathe-finance.com`
**rejette** ce cookie (domaine non suffixe de l'hôte) → aucune session stockée →
l'appel suivant part sans session → renvoi au login = **déconnexion immédiate**.

Sur horus ça marchait « par accident » : le défaut EST le domaine horus.

## Correctif permanent (code)
Ajout de `COOKIE_DOMAIN` à l'ancre `x-backend-env` dans
`infra/docker-compose.prod.yml` :
```yaml
COOKIE_DOMAIN: ${COOKIE_DOMAIN:-.gathe-finance.horus-lab.com}
```
Une fois sur `main`, le déploiement scp le compose et recrée le backend
(`--force-recreate` car le hash `infra/` change) → `COOKIE_DOMAIN` injecté.

## Déblocage immédiat sur le serveur cliente (sans attendre la CI)

```bash
cd /opt/gathe-finance/infra

# 1) Vérifier la valeur dans .env.prod (DOIT être .gathe-finance.com, point initial)
grep '^COOKIE_DOMAIN=' .env.prod
#   attendu : COOKIE_DOMAIN=.gathe-finance.com
#   si absent → l'ajouter ; si placeholder __CLIENT_DOMAIN__ → le remplacer

# 2) Patcher le compose pour transmettre la variable (jusqu'à ce que le prochain
#    déploiement apporte le correctif committé) — idempotent
grep -q 'COOKIE_DOMAIN' docker-compose.prod.yml || \
  sed -i '/^  CSRF_TRUSTED_ORIGINS:/a\  COOKIE_DOMAIN: ${COOKIE_DOMAIN:-.gathe-finance.horus-lab.com}' docker-compose.prod.yml

# 3) Recréer le backend (runtime env, pas de rebuild)
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  up -d --no-deps --force-recreate backend

# 4) Confirmer que Django a le bon domaine
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec -T backend python manage.py shell -c \
  "from django.conf import settings; print('SESSION_COOKIE_DOMAIN=', settings.SESSION_COOKIE_DOMAIN, '| CSRF_COOKIE_DOMAIN=', settings.CSRF_COOKIE_DOMAIN)"
#   attendu : SESSION_COOKIE_DOMAIN= .gathe-finance.com | CSRF_COOKIE_DOMAIN= .gathe-finance.com
```

Puis tester la connexion sur `https://admin.gathe-finance.com` (vider le cache /
cookies du site d'abord, pour purger l'ancien cookie horus éventuel).

## Vérification par en-tête (optionnel)
```bash
curl -si https://api.gathe-finance.com/api/v1/auth/csrf/ | grep -i 'set-cookie'
#   le Domain doit être .gathe-finance.com (PAS .horus-lab.com)
```

## Note
Le patch `sed` de l'étape 2 est un dépannage. Le prochain déploiement écrase
`docker-compose.prod.yml` par la version du repo — qui contient désormais la
ligne `COOKIE_DOMAIN` → aucun retour en arrière.
