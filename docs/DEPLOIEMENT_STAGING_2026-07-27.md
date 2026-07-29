# Runbook — Déploiement staging (2026-07-27)

Branche : `feat/credit-hardening-campaigns-cms-emails` → poussée sur `staging`.
PR : [#46](https://github.com/EdwinTchakounte/GatheFinance_project/pull/46).

## État (au 2026-07-27)
- ✅ **Code validé** : tous les tests + builds CI verts (backend pytest 10m, frontend, mobile, 4 images Docker sur GHCR).
- ✅ **Disque serveur nettoyé** (`docker system prune -af`) — le blocage « no space left on device » est levé.
- ✅ **DÉPLOIEMENT STAGING RÉUSSI** (rerun du run `30289252796`, `conclusion=success`). Le code est LIVE sur le staging Contabo (tag `:staging`).
- ⏳ **RESTE À FAIRE MAINTENANT → §3** : commandes de données sur le serveur (migrate + `seed_form_schemas --force` + réglages), puis smoke test (§4).

> §1 et §2 ci-dessous sont conservés pour référence (déjà faits).

---

## 1. Libérer l'espace disque (sur le serveur Contabo) — ✅ FAIT

```bash
ssh root@81.0.246.144        # host alias : afrikamode-vps

# Voir l'espace avant
df -h

# Nettoyer images / conteneurs / cache Docker inutilisés
docker system prune -af
docker builder prune -af

# Vérifier qu'il reste de la place
df -h
```

> ⚠️ **NE PAS** ajouter `--volumes` (`docker system prune -af --volumes`) : ça
> supprimerait les volumes = **données DB / médias**. Sans `--volumes`, c'est sûr
> (ne touche qu'aux images/conteneurs non référencés).

Si l'espace reste insuffisant après ça :
```bash
docker image prune -af          # images sans tag/non utilisées
du -sh /var/lib/docker/* | sort -h | tail   # repérer les gros postes
journalctl --vacuum-size=200M   # purge des logs systemd si volumineux
```

---

## 2. Relancer le déploiement — ✅ FAIT (rerun réussi)

Les images sont déjà construites sur GHCR → on relance **seulement** le job échoué :

```bash
gh run rerun 30289252796 --failed
# suivi :
gh run watch 30289252796
```

(ou pousser un commit vide sur `staging` pour re-déclencher tout le pipeline —
inutile ici, le rerun du job suffit.)

---

## 3. 👉 À FAIRE MAINTENANT — commandes de données (sur le serveur)

```bash
# Conteneur backend staging (adapter le nom si besoin)
docker exec -it gathe-finance-prod-backend-1 bash

python manage.py migrate                         # loans 0042/0043 · members 0020
python manage.py seed_form_schemas --force       # 🔴 OBLIGATOIRE (sinon voie BRC dégradée)
python manage.py bootstrap_site
python manage.py seed_blog
python manage.py seed_email_templates --force
```

Vérifier les **4 réglages gouvernance** effectifs (les re-poser si absents/legacy) :
- `loans.eligibility.apport_rate` = `0.30`
- `loans.apport.rate` = `0.20`
- `loans.apport.min_available_rate` (garde cagnotte)
- `loans.interest_withheld_at_source` = `true`

---

## 4. Smoke test staging (validation « en vrai »)

- Vitrine + portail + admin répondent (200).
- Adhésion : soumettre → approuver → payer 3 frais → membre ACTIF.
- Crédit voie apport : membre avec ≥ 30 % → demande 100 000 → gel 20 000, décaissé net 90 000, découvert 80 000.
- Carte admin « Exposition au découvert » affiche l'encours.

---

## 5. Passage en PROD (plus tard, même check-list)

Merge PR #46 → `main` → `deploy.yml` → VPS prod, PUIS **exactement les mêmes étapes**
qu'en §3 sur le serveur prod (migrate + `seed_form_schemas --force` + réglages).
+ **Briefer l'équipe crédit** (plancher 30 % / apport 20 % / intérêt source) et
**rebuild APK manuel avec FLAG_SECURE ON**.

Détails complets du lot : `docs/LIVRAISON_2026-07-27.md`.
