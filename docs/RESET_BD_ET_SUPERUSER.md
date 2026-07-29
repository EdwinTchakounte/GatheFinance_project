# Réinitialiser la base + créer un super-utilisateur

> ⚠️ **DESTRUCTIF ET IRRÉVERSIBLE.** Ces commandes **suppriment toutes les
> données** (membres, épargne, crédits, paiements, écritures…). À n'exécuter que
> sur une base que tu veux **repartir à zéro**. Fais une **sauvegarde** avant
> (voir §0) si tu as le moindre doute.

Toutes les commandes tournent dans le **conteneur backend** en prod. Préfixe :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py <cmd>
```

*(En local dev : `cd backend && DJANGO_SETTINGS_MODULE=config.settings.dev .venv/bin/python manage.py <cmd>`.)*

---

## 0. (Recommandé) Sauvegarde avant de tout effacer

```bash
# Dump complet de la base Postgres. Les identifiants sont lus depuis les
# variables du conteneur db ($POSTGRES_USER / $POSTGRES_DB), définies via .env.
docker compose -f infra/docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > backup_$(date +%F_%H%M).sql
```

---

## 1. Tout supprimer en base (garde le schéma + les migrations)

```bash
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py flush --no-input
```

`flush` vide **toutes les tables** puis restaure les données système
(ContentTypes, permissions). Le schéma et l'état des migrations restent
intacts — inutile de re-`migrate`.

> Variante « table rase totale » (recrée la base, plus radical que `flush`) :
> ```bash
> docker compose -f infra/docker-compose.prod.yml exec -T db \
>   sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"'
> docker compose -f infra/docker-compose.prod.yml exec backend \
>   python manage.py migrate
> ```

---

## 2. Re-semer les données de référence (indispensable après un flush)

Sans ça, l'app est vide et **inutilisable** (pas de frais, pas de réglages, pas
de templates e-mail…). En une ligne :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend sh -c '
  python manage.py seed_app_settings &&
  python manage.py seed_fees &&
  python manage.py seed_rates &&
  python manage.py seed_loan_tiers &&
  python manage.py seed_form_schemas &&
  python manage.py seed_event_catalog &&
  python manage.py seed_email_templates --force &&
  python manage.py seed_q_schedules
'
```

| Commande | Rôle |
|---|---|
| `seed_app_settings` | Tous les réglages métier (plafonds, taux, fenêtres, `notifications.ops_email`…) |
| `seed_fees` | Frais : adhésion 10 000 · inscription 2 000 · carnet 1 000 · étude crédit… |
| `seed_rates` | Taux d'intérêt / pénalités |
| `seed_loan_tiers` | Paliers de crédit (durée par montant) |
| `seed_form_schemas` | Schémas de formulaires (demande de crédit, adhésion…) |
| `seed_event_catalog` | Catalogue d'événements de notification |
| `seed_email_templates --force` | Templates e-mail (welcome, retrait, avaliste, apport…) |
| `seed_q_schedules` | Tâches planifiées (cron : collecte fin de mois, réinscription, maturité placement…) |

> **Ne PAS** lancer les `seed_demo_*` ni `seed_test_accounts` sur une prod
> propre — ce sont des données de démonstration/test.
>
> Après le seed, renseigne **`notifications.ops_email`** dans les réglages admin
> pour activer les alertes staff (cf. `ACTIONS_SERVEUR_POST_DEPLOY.md`).

---

## 3. Créer le super-utilisateur

### Interactif (demande login / e-mail / mot de passe)

```bash
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py createsuperuser
```

Renseigne un **e-mail** (la connexion admin/portail se fait par e-mail) et un
mot de passe fort.

### Non-interactif (scriptable — évite le mot de passe en clair dans l'historique)

```bash
docker compose -f infra/docker-compose.prod.yml exec \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=admin@gathe-finance.com \
  -e DJANGO_SUPERUSER_PASSWORD='RemplaceParUnMotDePasseFort' \
  backend python manage.py createsuperuser --no-input
```

---

## 4. Vérification

```bash
# Le superuser existe ?
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from django.contrib.auth import get_user_model as U; \
print(list(U().objects.filter(is_superuser=True).values_list('username','email')))"

# Les frais sont bien semés ?
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from apps_coop.payments.models import FeeType; \
print(list(FeeType.objects.values_list('code','montant')))"
```

Connecte-toi ensuite sur `https://admin.gathe-finance.horus-lab.com` avec
l'e-mail + mot de passe du superuser.

---

## Notes

- Le superuser a `is_staff=True` → accès complet au back-office (bypass RBAC).
- Un superuser n'est **pas** un `Member` : il n'a pas d'espace épargne/crédit.
  Pour ça, crée un membre via le parcours d'adhésion (ou l'admin).
- Le CMS (blog Wagtail) perd sa page racine au `flush` : si tu utilises le blog,
  recrée la racine via le Wagtail admin (`/cms/`) ou re-migre avec `--run-syncdb`.
