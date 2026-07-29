# Commandes post-déploiement staging — à lancer MAINTENANT

Staging déployé ✅ (tag `:staging`). Reste les commandes de données, sur le serveur.

## 1. Se connecter + entrer dans le conteneur backend

```bash
ssh root@81.0.246.144
docker exec -it gathe-finance-prod-backend-1 bash
```

## 2. Migrations + seeds (dans le conteneur)

```bash
python manage.py migrate
python manage.py seed_form_schemas --force
python manage.py bootstrap_site
python manage.py seed_blog
python manage.py seed_email_templates --force
```

> 🔴 `seed_form_schemas --force` est **obligatoire** : sans lui, les pièces BRC ne
> remontent plus à la file de validation (voie crédit dégradée).

## 3. Vérifier les 4 réglages gouvernance

Dans l'admin (Paramètres) **ou** en shell (`python manage.py shell`), s'assurer que :

| Réglage | Valeur attendue |
|---|---|
| `loans.eligibility.apport_rate` | `0.30` |
| `loans.apport.rate` | `0.20` |
| `loans.apport.min_available_rate` | (garde cagnotte) |
| `loans.interest_withheld_at_source` | `true` |

## 4. Smoke test (validation « en vrai »)

- Vitrine / portail / admin répondent (200).
- Adhésion : soumettre → approuver → payer 3 frais → membre **ACTIF**.
- Crédit voie apport : membre avec ≥ 30 % → demande 100 000 → **gel 20 000**, décaissé net **90 000**, découvert **80 000**.
- Carte admin « Exposition au découvert » affiche l'encours.

---

Runbook complet (contexte, disque, rerun, passage prod) : `docs/DEPLOIEMENT_STAGING_2026-07-27.md`.
