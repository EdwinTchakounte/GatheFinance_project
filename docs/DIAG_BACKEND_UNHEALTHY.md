# Diagnostic — backend jamais `healthy` (rollback auto)

## ✅ Où on en est (gros progrès)
Le déploiement va maintenant très loin :
- ✅ `docker login` GHCR OK · images `:main` **pull réussi**
- ✅ réseaux + volumes créés · **5 conteneurs Created + Started** (backend, qcluster, site, admin, portal)
- ❌ **seul échec** : le backend reste `starting` pendant 90 s (18/18) → jamais `healthy` → **rollback automatique**

## 🔴 Cause probable
Le backend démarre mais son healthcheck ne répond pas → presque toujours :
- il **n'arrive pas à joindre la base** (DATABASE_URL / Postgres injoignable), ou
- il **crashe au démarrage** (migration, variable d'env manquante).

---

## 🔎 Étape 1 — lire les logs du backend (LA commande clé)

Sur le serveur, en `gathe` :
```bash
cd /home/gathe/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod logs backend --tail 60
```
→ copier la sortie. Le message dira la cause exacte.

### Lecture des messages courants
| Message dans les logs | Cause | Correctif |
|---|---|---|
| `could not connect to server` / `Connection refused` | backend ne joint pas Postgres | `DATABASE_URL` (host/port) ou réseau `data` non attaché |
| `password authentication failed` | mauvais mot de passe | corriger `DATABASE_URL` (mot de passe du user `gathe`) |
| `database "gathe_prod" does not exist` | base non créée | `CREATE DATABASE gathe_prod;` (cf. bootstrap) |
| `role "gathe" does not exist` | user non créé | `CREATE USER gathe ...` + `GRANT` |
| `could not translate host name "<x>"` | mauvais **alias Postgres** dans `DATABASE_URL` | mettre l'alias réel (relevé `inspect-dmz.sh`) |
| Traceback Python (KeyError/ImproperlyConfigured) | variable d'env manquante | compléter `.env.prod` |

---

## 🔎 Étape 2 — vérifier réseaux & connectivité DB

```bash
# le backend est-il bien branché aux réseaux edge + data ?
docker inspect gathe-finance-prod-backend-1 \
  -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
#   attendu : quelque chose comme  ..._internal  <edge>  <data>

# les réseaux externes de la DMZ existent-ils ?
docker network ls | grep -iE 'edge|data'

# test direct : le backend peut-il joindre Postgres sur le réseau data ?
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend sh -lc 'python -c "import os;print(os.environ.get(\"DATABASE_URL\"))"'
#   -> confirme l'URL réellement vue par le backend

# ping applicatif de la base (depuis le backend) :
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend python manage.py showmigrations 2>&1 | head
#   -> si erreur DB, elle s'affiche ici
```

---

## 🔎 Étape 3 — vérifier `.env.prod` (valeurs DB/réseaux)

```bash
grep -E "^(DATABASE_URL|EDGE_NETWORK|DATA_NETWORK|AWS_S3_ENDPOINT_URL)=" /home/gathe/gathe-finance/infra/.env.prod
```
- `DATABASE_URL=postgres://gathe:<mdp>@<alias_postgres>:5432/gathe_prod` → `<alias_postgres>` doit être joignable sur `DATA_NETWORK`.
- `EDGE_NETWORK` / `DATA_NETWORK` = noms EXACTS (`docker network ls`).

---

## 🩹 Note — rollback

Le workflow a fait un rollback (`GATHE_IMAGE_TAG` remis à `main` + `up -d`). Les conteneurs peuvent tourner mais `unhealthy`. Une fois la cause corrigée, on relance le workflow (pas besoin de nettoyer à la main).

---

## ▶️ Ensuite
Coller les logs de l'**Étape 1** → correctif précis → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```

## Rappel — progression
| Étape | État |
|---|---|
| Clé SSH `gathe` · user `gathe` | ✅ |
| Upload infra · `.env.prod` propre | ✅ |
| `docker login ghcr.io` (gathe) · pull `:main` | ✅ |
| conteneurs démarrés | ✅ |
| **backend `healthy`** (DB/réseaux) | 🔧 ce document |
