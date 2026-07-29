# Actions prod — activer les corrections du 2026-07-22

Runbook **ordonné** pour rendre opérationnelles, sur la prod, toutes les
corrections de la session (voies crédit + formulaire + retrait + restitution
placement). À exécuter dans l'ordre. Préfixe commun :

```bash
cd /opt/gathe-finance   # (ou le dossier du repo sur le VPS)
```

> Rappel : `seed_app_settings` **n'écrase jamais** une valeur déjà en base → les
> réglages existants se corrigent à la main (étape 3). `seed_form_schemas
> --force`, lui, **republie** bien une nouvelle version.

---

## 1. Déployer la nouvelle image backend (code de la session)

Les correctifs **backend** (collecte `solde_disponible_retrait`, intérêt
placement à taux fixe + ligne capital, migration `savings/0019`, défaut du seed
`route_priority`) sont dans le **code** → il faut la nouvelle image.

```bash
git pull

docker compose -f infra/docker-compose.prod.yml up -d --build backend qcluster

# Migrations (nouveau TypeOp RESTITUTION_PLACEMENT → savings/0019)
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py migrate
```

*(Si tu déploies via la CI/CD `deploy.yml`, un `git push` sur `main` suffit —
elle build l'image, up -d, migre et fait le healthcheck.)*

---

## 2. Republier le schéma de demande de crédit

Réaffiche les sections **parcours / CGA / BRC** (une seule fois, pour **toutes
les voies**) et retire les doublons.

```bash
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py seed_form_schemas --force --only loan_request
```

---

## 3. Débloquer la voie GARANTIE (réglage en base — le seed ne l'écrase pas)

C'est **la** commande qui corrige « Aucune voie d'éligibilité ne s'applique ».

```bash
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.audit.models import AppSetting; AppSetting.objects.update_or_create(cle='loans.eligibility.route_priority', defaults={'valeur':'senior_brc,avaliste,garantie_materielle,campaign'}); print('OK', AppSetting.objects.get(cle='loans.eligibility.route_priority').valeur)"
```

Attendu : `OK senior_brc,avaliste,garantie_materielle,campaign`.

---

## 4. (Optionnel) Régler le taux d'intérêt de restitution placement

Défaut 1 %. Pour changer la valeur (le seed ne l'écrasera pas non plus) :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.audit.models import AppSetting; AppSetting.objects.update_or_create(cle='epargne.placement.interest_rate', defaults={'valeur':'0.01'}); print('OK', AppSetting.objects.get(cle='epargne.placement.interest_rate').valeur)"
```

---

## 5. Diagnostic AVALISTE (frais d'étude)

Pas un fix — vérifie pourquoi l'étape frais n'apparaissait pas.

```bash
# a) Valeur du frais d'étude
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.payments.models import FeeType; f=FeeType.objects.filter(code=FeeType.Code.DEMANDE_CREDIT).first(); print('montant', f.montant, 'actif', f.actif) if f else print('ABSENT')"
```

- `montant = 0` → l'étape frais est **sautée** volontairement : mettre un montant
  > 0 pour la voir (via l'admin ou `seed_fees` si absent).
- `montant > 0` mais l'étape n'apparaît toujours pas → l'image backend était
  antérieure au refactor « frais d'abord » : l'étape 1 (redéploiement) la corrige.

---

## 6. Vérification (les 4 voies)

```bash
# route_priority contient bien les 4 voies
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.audit.services import get_str_setting; print(get_str_setting('loans.eligibility.route_priority',''))"

# le schéma loan_request actif contient les sections parcours/CGA/BRC
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py shell -c \
"from apps_coop.forms.models import FormSchema; s=FormSchema.objects.filter(kind='loan_request', is_active=True).first(); print('sections:', [sec['id'] for sec in s.schema['sections']]) if s else print('AUCUN schéma actif')"
```

Attendu : les 4 voies dans `route_priority` ; `profil_apprenant`, `profil_cga`,
`profil_brc` présents dans les sections.

---

## 7. APK mobile

Les corrections **mobile** (card « Classique » retirée, champs parcours/BRC
re-rendus, retrait rafraîchi) ne sont visibles qu'avec un **nouvel APK release**.
Fichier livré : `~/Desktop/Gathe_finance/Gathe-Finance-1.0.0-prod.apk`.

---

## Récapitulatif « qui active quoi »

| Correction | Ce qui l'active en prod |
|---|---|
| Collecte `solde_disponible_retrait` | Étape 1 (déploiement) |
| Retrait — liste rafraîchie (mobile) | Étape 7 (APK) |
| Intérêt placement taux fixe + ligne capital | Étapes 1 + 4 |
| Sections parcours/CGA/BRC (toutes voies) | Étape 2 (+ APK) |
| **Voie GARANTIE débloquée** | **Étape 3** |
| Card « Classique » retirée | Étape 7 (APK) |
| Avaliste « frais d'abord » | Étapes 1 + 5 |
