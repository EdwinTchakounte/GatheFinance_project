# Notes opérationnelles VPS Contabo

Commandes à passer **sur le VPS** après un déploiement, pour pousser les
seeds (templates email, event catalog, cron schedules, etc.) que `migrate`
ne touche pas.

> Le déploiement (`deploy.yml`) ne fait **que** `git pull` + `docker compose
> pull` + `up -d` + healthcheck + nginx reload. Tout ce qui suit est à
> appliquer manuellement quand le code change un seed.

---

## Pré-requis (à faire une fois par session SSH)

```bash
ssh <VPS_USER>@<VPS_HOST>
cd /opt/gathe-finance/infra

# Alias pratique : COMPOSE inclut les 2 fichiers + le .env.prod.
export COMPOSE='docker compose -f docker-compose.prod.yml -f docker-compose.nginx-external.yml --env-file .env.prod'
```

Les containers prod sont préfixés `gathe-finance-prod-` (override via le
nom du projet compose). Si besoin de viser un container directement :

```bash
$COMPOSE ps                              # liste les services up
docker ps --filter name=gathe-finance    # tous les conteneurs GATHE
```

---

## 1) Reseed des templates email (après un changement dans `seed_email_templates.py`)

**À faire après le déploiement du commit `4784766` (PWD Option B)** pour que
le template `member.welcome` contienne le bouton « Définir mon mot de
passe ». Idempotent : `--force` réécrit les templates existants, n'effleure
pas le reste.

```bash
$COMPOSE exec backend python manage.py seed_email_templates --force
```

Sortie attendue : `↻ member.welcome (réécrit)` (et 14 autres lignes).

Si tu changes plus tard d'autres templates, relance la même commande.

---

## 2) Reseed du catalogue d'événements (nouveaux events)

Si le code ajoute un `emit_event("foo.bar")` sans qu'`EventConfig` /
`EventHook` existent en base, l'event est silencieusement ignoré. Cette
commande crée les lignes manquantes (sans toucher à celles déjà configurées
par l'admin).

```bash
$COMPOSE exec backend python manage.py seed_event_catalog
```

Events ajoutés récemment que tu peux vouloir activer :

- `lender.tranche_engaged` (notif au prêteur quand sa tranche est engagée)
- `member.reinscription_due_urgent` (rappel J-7)
- `member.reinscription_due_today` (rappel J0 anniversaire)
- `member.reinscription_expired_suspended` (suspension auto après grâce)

---

## 3) Reseed des FeeType / Rates (frais & taux par défaut)

Lancé automatiquement par l'entrypoint backend au boot. Idempotent —
ne ré-écrase rien que l'admin a déjà modifié via `/admin/coop/feetype/` ou
les écrans Next.js. Pas besoin de le rejouer manuellement après deploy
sauf si tu veux forcer.

Pour info, l'entrypoint exécute déjà :

```bash
python manage.py migrate
python manage.py seed_fees
python manage.py seed_rates
python manage.py seed_q_schedules    # cron django-q2
```

---

## 4) Tester le flow PWD Option B end-to-end

1. Approuver un nouveau membre via l'admin web (`https://admin.gathe-finance.horus-lab.com/membership-requests`).
2. Vérifier la réception de l'email (Brevo dashboard) avec le CTA primaire « Définir mon mot de passe ».
3. Suivre le lien → page `/definir-mot-de-passe?token=…`, poser un mdp.
4. Se connecter sur `/connexion` ou via l'app mobile avec email + mdp.
5. Payer les 3 frais (adhésion, inscription, carnet) → statut passe à `ACTIF`.

---

## 5) Rollback d'urgence (image précédente)

Si un deploy casse la prod et que le rollback auto de `deploy.yml` n'a pas
suffi, repointer manuellement vers une image précédente :

```bash
# Récupérer le SHA d'une image stable depuis GHCR.
ssh <VPS_USER>@<VPS_HOST>
cd /opt/gathe-finance/infra

# Editer .env.prod et pinner GATHE_IMAGE_TAG=sha-XXXX (ou main).
sed -i.bak 's/^GATHE_IMAGE_TAG=.*/GATHE_IMAGE_TAG=sha-XXXX/' .env.prod

$COMPOSE pull
$COMPOSE up -d
docker restart backend-nginx-1
```

---

## 6) Logs & debug rapide

```bash
$COMPOSE logs -f backend --tail=100      # logs Django temps réel
$COMPOSE logs -f qcluster --tail=100     # logs cron django-q2
docker logs -f backend-nginx-1           # reverse proxy mutualisé

# Shell Django dans le container.
$COMPOSE exec backend python manage.py shell

# Inspecter un seed effectué.
$COMPOSE exec backend python manage.py shell -c \
  "from apps_coop.notifications.models import EmailTemplate; \
   print(EmailTemplate.objects.get(code='member.welcome').objet)"
```

---

## 7) Variables à NE JAMAIS toucher en prod

- `PAYMENTS_TEST_AUTO_VALIDATE` : doit rester `false` (sinon paiements
  auto-validés sans Tara → trou caisse).
- `DEBUG=False`, `ALLOWED_HOSTS=*.gathe-finance.horus-lab.com`.
- `SESSION_COOKIE_DOMAIN=.gathe-finance.horus-lab.com` (cross-subdomain).
- Clé Brevo, secret Tara, `DJANGO_SECRET_KEY` : dans `.env.prod` uniquement,
  jamais commit.

---

## 8) Repli SMTP quand Brevo échoue (voie de secours)

Les e-mails de la coopérative sont **critiques** (mot de passe, activation,
échéance J-3, saisie sur épargne) : si Brevo tombe — quota mensuel épuisé, clé
révoquée, compte suspendu pour réputation, API indisponible — le message est
**rejoué sur un SMTP de secours** au lieu d'être perdu.

> ⚠️ La délivrabilité de la voie de secours est **dégradée : l'e-mail partira
> probablement en spam**. C'est un compromis assumé — un e-mail en spam reste
> récupérable par le membre, un e-mail jamais parti ne l'est pas.

### Activer

Dans `.env.prod`, renseigner le SMTP de secours puis redémarrer le backend :

```bash
EMAIL_FALLBACK_SMTP_HOST=smtp.exemple-nhr.com
EMAIL_FALLBACK_SMTP_PORT=587
EMAIL_FALLBACK_SMTP_USER=...
EMAIL_FALLBACK_SMTP_PASSWORD=...
EMAIL_FALLBACK_SMTP_USE_TLS=true
# Si ce SMTP n'autorise que ses propres adresses en From: (rejet 550 sinon).
# L'expéditeur GATHE est alors conservé en Reply-To.
EMAIL_FALLBACK_FROM="NHR <no-reply@exemple-nhr.com>"

$COMPOSE up -d backend qcluster
```

**`EMAIL_FALLBACK_SMTP_HOST` vide = AUCUN repli** : le backend délègue tout à
Brevo, comportement strictement identique à avant. C'est le cas en dev et en CI.

### Vérifier quels e-mails sont passés par le secours

Le mode dégradé est **visible**, pas silencieux :

- Dashboard admin → **Supervision** → colonne Statut, badge « Voie de secours ».
- Django admin → *Emails envoyés* → filtre `transport`.
- En shell :

```bash
$COMPOSE exec backend python manage.py shell -c \
  "from apps_coop.notifications.models import EmailLog; \
   print(EmailLog.objects.filter(transport='fallback').count())"
```

Un compteur qui grimpe = **Brevo est en panne ou à bout de quota**, à traiter :
le secours est un filet, pas un régime de croisière.

### Tester le repli sans casser Brevo

Poser une fausse clé API le temps d'un envoi (les messages basculent tous sur le
secours), puis remettre la vraie :

```bash
$COMPOSE exec -e BREVO_API_KEY=invalide backend python manage.py shell -c \
  "from apps_coop.notifications.services import send_template; \
   print(send_template('member.welcome', to='toi@exemple.com').transport)"
# attendu : fallback
```

Mécanique : `apps_coop/notifications/email_backends.py` (`FailoverEmailBackend`,
posé sur `EMAIL_BACKEND` par `config/settings/prod.py`). Le repli est décidé
**message par message** : dans un lot, seuls les messages tombés sont rejoués.
