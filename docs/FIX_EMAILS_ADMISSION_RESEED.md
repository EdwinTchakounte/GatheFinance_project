# FIX — E-mails d'admission déphasés chez la cliente (re-seed templates)

## Cause racine

Les **templates d'e-mail** vivent en base (`EmailTemplate`). Ils sont semés par
la commande `seed_email_templates` en **`get_or_create`** : sans `--force`, elle
**ne met PAS à jour** les templates déjà présents.

`docker-entrypoint.sh` **ne lance jamais** `seed_email_templates` (vérifié). Les
templates n'ont donc été semés qu'**une seule fois** (anciennes versions) et
jamais rafraîchis → la base cliente sert les **vieux e-mails**, alors que le
**code contient déjà les bonnes versions** (flux 3 frais, sans entretien).

## Audit — phases d'admission ↔ e-mails (le CODE est correct)

| Phase | Statut membre | E-mail | Code template | Déclencheur | État (code) |
|---|---|---|---|---|---|
| Soumission (vitrine/mobile) | demande `en_attente` | *(aucun — accusé à l'écran)* | — | — | OK |
| **Approbation** (comité) | `SUSPENDU` (attend 3 frais) | Bienvenue + n° membre + **3 frais** + définir mot de passe | `member.welcome` | `members/services.py:361` | ✅ à jour |
| **Paiement des 3 frais** complet | `ACTIF` | Compte activé | `member.activated` | `payments/services.py:411` | ✅ à jour |
| **Rejet** | rejeté | Demande non retenue + motif | `member.rejected` | `members/services.py:426` | ✅ à jour |
| ~~Entretien d'admission~~ | — | — | `membership.interview_scheduled` | **jamais émis** | ⚠️ obsolète (entretien supprimé 2026-07-09) |

→ Aucun e-mail d'admission ne manque et aucun ne référence l'ancien flux **dans
le code**. Le déphasage est **uniquement en base cliente**.

## Update 1 — OBLIGATOIRE (serveur) : re-seed en `--force`

Sur le serveur cliente, en SSH :

```bash
cd /home/gathe/gathe-finance/infra
alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod'
```

**a) Voir l'état AVANT** (objet + date de mise à jour) :
```bash
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; [print(t.code,'|',repr(t.objet),'| maj', t.updated_at) for t in T.objects.filter(code__in=['member.welcome','member.activated','member.rejected']).order_by('code')]"
```
→ Note les `objet` et `maj` actuels (probablement anciens libellés, date ancienne).

**b) Appliquer la mise à jour** :
```bash
dc exec backend python manage.py seed_email_templates --force
```
→ Sortie attendue : `0 créé(s), N réécrit(s), 0 skipped.` (N = nb de templates).

**c) Vérifier APRÈS** (mêmes lignes, `objet` et `maj` doivent avoir changé) :
```bash
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; t=T.objects.get(code='member.welcome'); print(t.objet); print('---'); print(t.corps_html[:400])"
```
→ Doit afficher **« Ta demande d'adhésion est approuvée »** + les **3 frais**
(adhésion / inscription / carnet) + le bouton **Définir mon mot de passe**.

> Aucune reconstruction/déploiement nécessaire : l'image backend cliente contient
> déjà les bons templates ; on ne fait que rafraîchir la base.

## Update 2 — OPTIONNEL (code) : nettoyage du déphasage résiduel

Purement cosmétique (n'affecte pas les e-mails envoyés) :
1. Retirer le template mort `membership.interview_scheduled` de
   `seed_email_templates.py` (l.124).
2. Corriger les libellés obsolètes du **catalogue d'événements**
   (`seed_event_catalog.py`) : la description de `member.activated` dit encore
   « après l'entretien d'admission » ; l'entrée `membership.interview_scheduled`
   à retirer.

À déployer via PR si souhaité (sinon sans impact — l'entretien n'est jamais émis).

## Vérification finale (facultative)

Faire une **nouvelle demande d'adhésion de bout en bout** (vitrine → approbation
admin → paiement des 3 frais) et vérifier les 2 e-mails reçus :
- à l'approbation : « Ta demande d'adhésion est approuvée » + 3 frais + lien
  définir mot de passe ;
- au paiement complet : « Ton compte GATHE Finance est actif ».
