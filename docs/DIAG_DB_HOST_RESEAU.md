# Diagnostic — backend ne joint pas Postgres (hôte / réseau)

## Constat
Logs backend :
```
[entrypoint] waiting for database... database did not become available
```
Config lue par le backend :
```
DATABASE_URL=postgres://gathe:***@postgres:5432/gathe_prod
```
→ il cherche un hôte **`postgres`** sur le réseau `data`.

Vérifs déjà faites :
- backend attaché à `data` + `edge` ✅  (`docker inspect ...-backend-1` → `data edge ..._internal ..._web`)
- réseaux `data` et `edge` existent ✅
- ⇒ **donc** : soit le conteneur Postgres **n'est pas sur `data`**, soit son **alias n'est pas `postgres`**.

> 🔐 Le mot de passe DB a été affiché en clair → à changer une fois le déploiement stable.

---

## 🔎 Étape 1 — localiser le conteneur Postgres (réseau + alias)

```bash
docker ps --format '{{.Names}}' | grep -iE 'postgres|pg|db'

docker inspect postgres \
  -f '{{range $k,$v := .NetworkSettings.Networks}}reseau={{$k}} alias={{range $v.Aliases}}{{.}} {{end}}{{println}}{{end}}'
```
Noter :
- **sur quel réseau** est Postgres (est-ce bien `data` ?)
- **quel alias** il porte (c'est l'hôte à mettre dans `DATABASE_URL`)

---

## 🔎 Étape 2 — tester depuis le backend

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod \
  exec backend sh -lc 'getent hosts postgres || echo "HOST postgres INCONNU"; \
  python -c "import socket; socket.create_connection((\"postgres\",5432),5); print(\"port 5432 JOIGNABLE\")" 2>&1'
```
- `HOST postgres INCONNU` → l'alias `postgres` n'existe pas sur le réseau du backend.
- `port 5432 JOIGNABLE` → réseau OK, le souci serait ailleurs (auth/db).

---

## 🎯 Les 2 scénarios & correctifs

### Scénario A — Postgres n'est PAS sur `data`
Le réseau `data` que tu as (peut-être créé vide) n'est pas celui de leur Postgres.
→ Dans `.env.prod`, mettre le **vrai** réseau de Postgres :
```bash
# valeur = le "reseau=" affiché à l'étape 1 pour le conteneur Postgres
sed -i 's/^DATA_NETWORK=.*/DATA_NETWORK=data/' /home/gathe/gathe-finance/infra/.env.prod
```
*(le backend rejoindra alors le réseau où vit réellement Postgres.)*

### Scénario B — Postgres est sur `data` mais alias ≠ `postgres`
Ex. alias réel `services-postgres-1` ou `db`.
→ Corriger l'hôte dans `DATABASE_URL` :
```bash
# remplacer @postgres: par @<bon_alias>:
sed -i 's#@postgres:5432#@postgres:5432#' /home/gathe/gathe-finance/infra/.env.prod
grep ^DATABASE_URL= /home/gathe/gathe-finance/infra/.env.prod   # vérifier
```

*(Les deux peuvent se combiner : bon réseau **et** bon alias.)*

---

## ✅ Re-tester en local avant de relancer le workflow

```bash
cd /home/gathe/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod up -d --no-deps backend
sleep 15
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod logs backend --tail 20
#   -> on veut voir la fin du "waiting for database" + les migrations qui démarrent
```
Si le backend passe le "waiting for database" → c'est bon.

---

## ▶️ Ensuite
Dire « DB OK » → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```

## Rappel — progression
| Étape | État |
|---|---|
| SSH `gathe` · user · upload · `.env.prod` · GHCR login · pull · conteneurs Up | ✅ |
| **backend joint Postgres (hôte/réseau)** | 🔧 ce document |
| backend `healthy` → smoke tests | à suivre |
