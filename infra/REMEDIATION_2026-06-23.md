# Plan de remediation post-audit du 23 juin 2026

> Application des patches identifies par l'audit
> `AUDIT-GF-2026-06-23-DEP` (Groupe Horus-lab).

## Synthese des findings traites

| ID | Severite | Domaine | Action retenue |
|---|---|---|---|
| F-01 | MAJEUR | Admin — HTTP 400 sur /api/v1/* | Patch backend prod.py + .env.prod |
| F-02 | MAJEUR | Admin — loading infini | Patch admin layout.tsx (redirect /login sur toute erreur) |
| F-03 | (faux positif) | Portail | Les routes sont en francais (/connexion, /epargne...). Aucune action |
| F-04 | MINEUR | CMS racine cms.*/ redirige vers vitrine | Report — non bloquant |
| F-05 | MINEUR | Mobile 62 warnings | Report — chantier dedie |

## 1. Diagnostic prealable (sur le VPS)

Avant d'appliquer, verifie l'etat des variables d'environnement dans le
conteneur backend :

```bash
docker exec gathe-finance-prod-backend-1 \
  python -c "from django.conf import settings; print('ALLOWED_HOSTS =', settings.ALLOWED_HOSTS); print('CSRF =', settings.CSRF_TRUSTED_ORIGINS)"
```

Si tu vois que `gathe-backend` est absent d'`ALLOWED_HOSTS` ou que
`CSRF_TRUSTED_ORIGINS` ne contient pas
`https://admin.gathe-finance.horus-lab.com`, c'est la cause racine du 400.
Les patches ci-dessous le corrigent durablement.

## 2. Patches appliques au code (deja committes localement)

Les modifications suivantes existent deja sur ta branche `main` :

### 2.1 `backend/config/settings/prod.py`

Auto-injection des hosts internes et auto-derivation de
`CSRF_TRUSTED_ORIGINS` :

```python
_INTERNAL_HOSTS = ["gathe-backend", "backend", "localhost", "127.0.0.1"]
for _host in _INTERNAL_HOSTS:
    if _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

_PUBLIC_HOSTS = [h for h in ALLOWED_HOSTS
                 if h not in _INTERNAL_HOSTS
                 and not h.replace(".", "").isdigit()]
for _host in _PUBLIC_HOSTS:
    _origin = f"https://{_host}"
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)
```

Apres ce patch, la stack reste fonctionnelle meme si l'override
`docker-compose.nginx-external.yml` n'est pas applique au lancement.

### 2.2 `frontend/apps/admin/app/(authed)/layout.tsx`

La garde d'authentification redirige vers `/login` sur **toute**
reponse en erreur (pas seulement 401/403). Plus de page blanche
quand le proxy retourne 400 ou 500 :

```typescript
if (typeof apiErr?.status === "number") {
  router.replace("/login");
} else {
  router.replace("/login?reason=network");
}
```

### 2.3 `infra/.env.prod.example`

Ajout d'une entree `CSRF_TRUSTED_ORIGINS` explicite a renseigner
dans le `.env.prod` du VPS.

## 3. Mise en oeuvre sur le VPS

### 3.1 Mettre a jour le code

Une fois les patches pousses sur GitHub, sur le VPS :

```bash
cd /opt/gathe-finance
git pull origin main
cd infra
```

### 3.2 Ajouter `CSRF_TRUSTED_ORIGINS` au `.env.prod`

```bash
# Verifier si la ligne existe deja
grep ^CSRF_TRUSTED_ORIGINS /opt/gathe-finance/infra/.env.prod || \
  cat >> /opt/gathe-finance/infra/.env.prod <<'EOF'

# CSRF_TRUSTED_ORIGINS — obligatoire pour les POST/PATCH/DELETE depuis
# admin et portail. Auto-derive dans prod.py si vide, mais explicite ici.
CSRF_TRUSTED_ORIGINS=https://gathe-finance.horus-lab.com,https://portail.gathe-finance.horus-lab.com,https://admin.gathe-finance.horus-lab.com,https://api.gathe-finance.horus-lab.com,https://cms.gathe-finance.horus-lab.com
EOF
```

### 3.3 Tirer la nouvelle image backend

Une fois le CI verte sur GitHub (workflow `ci.yml` a tourne, image
`ghcr.io/.../backend:latest` mise a jour) :

```bash
cd /opt/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml \
  --env-file .env.prod pull backend qcluster
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml \
  --env-file .env.prod up -d --force-recreate backend qcluster
```

### 3.4 Tirer la nouvelle image admin

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml \
  --env-file .env.prod pull admin
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml \
  --env-file .env.prod up -d --force-recreate admin
```

### 3.5 Reload nginx

```bash
docker restart backend-nginx-1
```

## 4. Validation post-deploiement

### 4.1 Verifier les nouveaux ALLOWED_HOSTS

```bash
docker exec gathe-finance-prod-backend-1 \
  python -c "from django.conf import settings; print(settings.ALLOWED_HOSTS); print(settings.CSRF_TRUSTED_ORIGINS)"
```

Attendu :
- `ALLOWED_HOSTS` contient `gathe-backend`, `localhost`,
  `127.0.0.1` plus les 5 sous-domaines
- `CSRF_TRUSTED_ORIGINS` contient les 5 origines HTTPS

### 4.2 Smoke tests api → admin

```bash
# Direct api → doit etre 403 (auth requise) — etat sain
curl -sIL https://api.gathe-finance.horus-lab.com/api/v1/auth/me/ | head -2

# Via le rewrite admin → doit aussi etre 403 (et plus 400 / 500)
curl -sIL https://admin.gathe-finance.horus-lab.com/api/v1/auth/me/ | head -2
```

### 4.3 Test navigateur

1. Ouvre `https://admin.gathe-finance.horus-lab.com/` en navigation
   privee.
2. Verifie que l'application redirige **automatiquement** vers
   `/login` (et n'affiche plus l'ecran "Chargement..." infini).
3. Authentifie-toi avec le superuser admin (`admin@horus-lab.com` +
   `DJANGO_SUPERUSER_PASSWORD` du `.env.prod`).
4. Le tableau de bord doit charger les KPI sans erreur console.

## 5. En cas de blocage residuel

### 5.1 Erreur persiste apres pull

Force la recreation des deux services :

```bash
cd /opt/gathe-finance/infra
docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml \
  --env-file .env.prod up -d --force-recreate --no-deps backend qcluster admin
```

### 5.2 La page tourne en boucle redirect /login

Le navigateur a peut-etre un ancien cookie de session invalide.
Ouvrir une session privee, ou vider les cookies du domaine
`*.gathe-finance.horus-lab.com`.

### 5.3 Le rewrite continue de retourner 400

Verifier le DATABASE_URL et le mot de passe Postgres dans le
conteneur backend :

```bash
docker exec gathe-finance-prod-backend-1 env | grep -E "DATABASE_URL|ALLOWED_HOSTS"
```

Si DATABASE_URL contient des caracteres speciaux, suivre la
procedure du rapport `AUDIT_DEPLOIEMENT_2026-06-23.pdf` section 6.3.

## 6. Findings reportes

| ID | Severite | Decision |
|---|---|---|
| F-04 (CMS racine) | MINEUR | A traiter lors du prochain sprint frontend |
| F-05 (mobile warnings) | MINEUR | Chantier dedie cleanup `unawaited_futures` |
| F-06 (backups hors-VPS) | INFO | Planifier le push rsync vers Backblaze |
| F-07 (CD auto) | INFO | Poser les 3 secrets GitHub apres validation manuelle |
| F-08 (webhook Tara) | INFO | Action exploitant — declarer URL dans dashboard |
| F-09 (Brevo sender) | INFO | Action exploitant — verifier DKIM/SPF |

---

Documents lies :
- `audit/AUDIT_DEPLOIEMENT_2026-06-23.pdf` — rapport complet
- `audit/AUDIT_DEPLOIEMENT_2026-06-23.md` — version Markdown
- `audit/build_audit_pdf.py` — generateur PDF
