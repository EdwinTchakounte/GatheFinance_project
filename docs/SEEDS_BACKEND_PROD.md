# Seeds backend prod — à lancer après déploiement

But : finaliser les données après `migrate` (schémas de formulaires BRC, CMS Wagtail, templates emails).

> ⚠️ `root@vmi3289409:~#` = l'HÔTE (pas de `manage.py`, pas de `python`).
> Il faut d'abord ENTRER dans le conteneur (prompt attendu `root@…:/app#`).
> À l'intérieur : `python` (pas `python3`), et lancer les commandes **une par une**.

## Étape 1 — entrer dans le conteneur

```bash
docker exec -it gathe-finance-prod-backend-1 bash
```

## Étape 2 — au prompt `root@…:/app#`, lancer une par une

```bash
python manage.py seed_form_schemas --force
```

```bash
python manage.py bootstrap_site
```

```bash
python manage.py seed_blog
```

```bash
python manage.py seed_email_templates --force
```

## Sorties attendues

| Commande | OK si… | Rôle |
|---|---|---|
| `seed_form_schemas --force` | (ré)écriture des schémas, pas de traceback | sans lui, pièces BRC ne remontent pas à la validation |
| `bootstrap_site` | Locales fr/en + HomePage + BlogIndex + Site, **fin sans 500** | répare le CMS Wagtail (articles / éditeur) |
| `seed_blog` | articles seedés (fr/en) | contenu vitrine |
| `seed_email_templates --force` | ~15 templates (ré)écrits | corrige les liens des emails |

⚠️ Point sensible = **`bootstrap_site`** : s'il crache un traceback, c'est le bug CMS Wagtail → capturer la sortie complète pour correctif.

## Après les seeds — vérifier les AppSettings

Dans l'admin (Paramètres) ou en shell, s'assurer que :

| Réglage | Valeur |
|---|---|
| `loans.eligibility.apport_rate` | `0.30` |
| `loans.apport.rate` | `0.20` |
| `loans.apport.min_available_rate` | `0.10` |
| `loans.interest_withheld_at_source` | `true` |
| `notifications.admin_url` | domaine admin |
| `collecte.monthly.commission_rate` | `0.01` |
