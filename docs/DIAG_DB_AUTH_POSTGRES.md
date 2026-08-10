# Diagnostic — connexion DB refusée (auth / base / user)

## Constat (le réseau est BON)
- `postgres` résout (`172.19.0.3`) et **port 5432 JOIGNABLE** ✅
- Mais l'entrypoint backend (qui se connecte via **Django / `DATABASE_URL`**) échoue :
  `[entrypoint] database did not become available`

→ Ce n'est plus le réseau : c'est **l'authentification / la base / le user**.

L'entrypoint fait :
```python
django.setup(); connections["default"].cursor()   # OperationalError si auth/base KO
```

> ⚠️ Le mot de passe dans `DATABASE_URL` semble contenir une **coquille** (`…jkjkhdfdfdwhln…`) → mismatch mot de passe très probable.
> 🔐 Ce mot de passe a été affiché en clair → à changer une fois stable.

---

## 🔎 Test décisif — obtenir la vraie erreur Postgres

```bash
# 1) le mot de passe EXACT présent dans .env.prod
grep ^DATABASE_URL= /home/gathe/gathe-finance/infra/.env.prod

# 2) tenter la connexion réelle avec ce mot de passe
docker exec -e PGPASSWORD='Bz6Z5GNJXj7c3uVwhlnRVlefcuIA28' postgres \
  psql -U gathe -d gathe_prod -c 'select 1;'
```

### Lecture du résultat
| Résultat commande 2 | Cause | Fix |
|---|---|---|
| ` 1 ` (une ligne) | connexion OK | rien — relancer le backend |
| `FATAL: password authentication failed for user "gathe"` | **mot de passe ≠** Postgres | aligner (§A) |
| `FATAL: database "gathe_prod" does not exist` | base absente | §B |
| `FATAL: role "gathe" does not exist` | user absent | §C |

---

## §A — Aligner le mot de passe (cas le plus probable)
Forcer le mot de passe Postgres = **exactement** celui du `.env.prod` :
```bash
docker exec -it postgres psql -U postgres \
  -c "ALTER USER gathe WITH PASSWORD 'Bz6Z5GNJXj7c3uVwhlnRVlefcuIA28';"
```
*(copier le mot de passe tel quel depuis la commande 1 — l'essentiel : les deux côtés identiques.)*

## §B — Créer la base
```bash
docker exec -it postgres psql -U postgres -c "CREATE DATABASE gathe_prod OWNER gathe;"
```

## §C — Créer le user + droits
```bash
docker exec -it postgres psql -U postgres -c "CREATE USER gathe WITH PASSWORD 'Bz6Z5GNJXj7c3uVwhlnRVlefcuIA28';"
docker exec -it postgres psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE gathe_prod TO gathe;"
# (si la base existe déjà mais sans owner gathe)
docker exec -it postgres psql -U postgres -c "ALTER DATABASE gathe_prod OWNER TO gathe;"
```

---

## ✅ Re-tester puis valider

```bash
cd /home/gathe/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod up -d --no-deps backend
sleep 15
docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod logs backend --tail 15
```
Attendu dans les logs :
```
[entrypoint] database is up
[entrypoint] applying migrations...
```

---

## ▶️ Ensuite
Dès « database is up » → dire « DB OK » → relance :
```bash
gh workflow run deploy.yml -f image_tag=main
```
→ le backend passera `healthy` → smoke tests → **en ligne**.

## Rappel — progression
| Étape | État |
|---|---|
| SSH · user · upload · `.env.prod` · GHCR · pull · conteneurs Up · réseau data/edge · port 5432 | ✅ |
| **auth DB (mot de passe / base / user)** | 🔧 ce document |
| backend `healthy` → smoke tests | à suivre |
