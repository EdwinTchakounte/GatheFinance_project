# Commandes prod — retirer la section « Rattachement BRC »

La section vient du **schéma de formulaire en base de prod** (pas du build mobile).
Le code qui la retire est **déjà déployé** (PR #44, CI « Deploy to prod » OK le
2026-07-23). Il reste **une seule chose** : **republier le schéma** en base.

> ⚠️ Sur CE serveur, toute commande docker compose = **les 2 fichiers compose**
> (`prod` + `nginx-external`) **+ `--env-file infra/.env.prod`**. Jamais un seul,
> jamais `--build`, jamais `git pull`. Cf. `docs/DEPLOIEMENT_SERVEUR_GATHE.md`.

Préfixe (optionnel — raccourci de session) :
```bash
cd /opt/gathe-finance
DC="docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod"
```

---

## 1. Republier le schéma (retire `profil_brc`)

```bash
cd /opt/gathe-finance
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod exec backend python manage.py seed_form_schemas --force --only loan_request
```

*(avec l'alias : `$DC exec backend python manage.py seed_form_schemas --force --only loan_request`)*

Sortie attendue : `✓ loan_request vX → vX+1 (remplacée).`

---

## 2. Vérifier que la section est bien partie

### Option A — endpoint public (depuis n'importe où, SANS SSH) — RECOMMANDÉ

```bash
curl -s https://api.gathe-finance.horus-lab.com/api/v1/forms/schemas/loan_request/active/ \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([s['id'] for s in d.get('schema',d)['sections']])"
```

Attendu : `['demande', 'modalite', 'profil_apprenant', 'profil_cga']`
→ **`profil_brc` ABSENT**. (Tant qu'on voit encore `profil_brc`, le reseed n'a pas
été lancé.)

### Option B — en base (dans le conteneur)

```bash
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod exec backend python manage.py shell -c "from apps_coop.forms.models import FormSchema; s=FormSchema.objects.filter(kind='loan_request', is_active=True).first(); print([sec['id'] for sec in s.schema['sections']])"
```

Puis, sur le mobile / portail : rouvrir une demande de crédit → la section
« Rattachement Broad Range Consulting » ne doit plus apparaître.
*(Aucun rebuild d'APK nécessaire pour ce point — c'est backend.)*

---

## Autre réglage prod encore en attente (voie Garantie)

Indépendant du BRC. Le seed n'écrase pas une valeur existante → mise à jour
manuelle en base :

```bash
docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.nginx-external.yml --env-file infra/.env.prod exec backend python manage.py shell -c "from apps_coop.audit.models import AppSetting; AppSetting.objects.update_or_create(cle='loans.eligibility.route_priority', defaults={'valeur':'senior_brc,avaliste,garantie_materielle,campaign'}); print('OK', AppSetting.objects.get(cle='loans.eligibility.route_priority').valeur)"
```

Attendu : `OK senior_brc,avaliste,garantie_materielle,campaign`.
