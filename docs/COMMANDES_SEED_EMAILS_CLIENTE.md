# Commandes — Rafraîchir les e-mails d'admission (serveur cliente)

> À lancer **APRÈS le déploiement de la PR #60**, sur le serveur cliente en SSH.
> Objectif : remplacer les anciens templates par les versions à jour + créer les
> nouveaux (contre-proposition), et aligner le catalogue d'événements.

## 0. Préparation

```bash
cd /home/gathe/gathe-finance/infra
alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod'
```

## 1. (AVANT) — voir l'état actuel des templates d'admission

```bash
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; [print(t.code,'|',repr(t.objet),'| maj',t.updated_at) for t in T.objects.filter(code__in=['member.welcome','member.activated','member.rejected']).order_by('code')]"
```

## 2. Appliquer la mise à jour (LES 2 commandes)

```bash
# a) réécrit TOUS les templates existants + crée les nouveaux (dont contre-proposition)
dc exec backend python manage.py seed_email_templates --force

# b) aligne le catalogue d'événements (libellés + nouvel événement)
dc exec backend python manage.py seed_event_catalog
```

Sortie attendue (a) : `0 créé(s), N réécrit(s), 0 skipped.` — **ou** `1 créé(s)`
si le template contre-proposition n'existait pas encore.

## 3. (APRÈS) — vérifier

```bash
# le welcome doit afficher les 3 frais + définir mot de passe
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; t=T.objects.get(code='member.welcome'); print(t.objet); print(t.corps_html[:400])"

# le nouveau template contre-proposition doit exister
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; print(T.objects.filter(code='loan_request.counter_proposal_accepted').exists())"

# l'ancien template entretien ne doit plus être servi (peut rester en base, inoffensif)
dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; print('interview encore en base:', T.objects.filter(code='membership.interview_scheduled').exists())"
```

Attendu :
- welcome → objet **« Ta demande d'adhésion est approuvée »**, corps avec **3 frais** (adhésion / inscription / carnet) + bouton **Définir mon mot de passe** ;
- contre-proposition → `True` ;
- entretien → peut rester `True` en base (template mort, plus jamais émis) ; on peut l'ignorer, ou le supprimer manuellement si on veut un catalogue propre :
  ```bash
  dc exec backend python manage.py shell -c "from apps_coop.notifications.models import EmailTemplate as T; n=T.objects.filter(code='membership.interview_scheduled').delete(); print('supprimé:', n)"
  ```

## 4. Test de bout en bout (recommandé)

Faire une **nouvelle demande d'adhésion** (vitrine → approbation admin → paiement
des 3 frais) et vérifier les 2 e-mails reçus :
- à l'approbation : « Ta demande d'adhésion est approuvée » + 3 frais + lien mot de passe ;
- au paiement complet : « Ton compte GATHE Finance est actif ».

---

Réf. audit complet : `docs/FIX_EMAILS_ADMISSION_RESEED.md`.
