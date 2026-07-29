# Activer les e-mails en prod (seed notifications)

Commandes à lancer sur le serveur pour que les e-mails partent (catalogue
d'événements + templates + réglages). Idempotent — sans danger de re-lancer.

> Prérequis : la **clé API Brevo** doit être posée sur le serveur (variable
> d'env). C'est l'API HTTP qui envoie réellement les mails. Sans clé, les envois
> sont journalisés en échec mais ne partent pas.

---

## 1. Seed (dans le conteneur backend)

```bash
# Catalogue d'événements — ajoute les nouveaux : retrait à traiter, dossier
# crédit prêt, crédit soldé, caution avaliste libérée, part de placement
# libérée, apport prêteur.
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py seed_event_catalog

# Templates e-mail — --force réécrit les existants + ajoute les nouveaux.
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py seed_email_templates --force

# Réglages — ajoute notifications.ops_email et notifications.admin_url.
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py seed_app_settings
```

Ou en une seule commande :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend sh -c '
  python manage.py seed_event_catalog &&
  python manage.py seed_email_templates --force &&
  python manage.py seed_app_settings
'
```

*(En local dev : `cd backend && DJANGO_SETTINGS_MODULE=config.settings.dev .venv/bin/python manage.py <cmd>`.)*

---

## 2. Renseigner l'adresse de l'équipe (`notifications.ops_email`)

### C'est quoi ?

`notifications.ops_email` = **l'adresse e-mail de l'équipe interne** (la coop)
vers laquelle partent les **alertes de gestion** (« il y a quelque chose à
traiter »). Il y a deux familles d'e-mails dans le système :

- **E-mails aux membres** (prêteurs, garants…) → adressés à *leur* propre
  adresse. Ex : « votre retrait est validé », « votre crédit est soldé ».
  → **Fonctionnent déjà, ne dépendent PAS de ce réglage.**
- **E-mails à l'équipe (ops)** → adressés à `notifications.ops_email`. Ce sont
  des notifications de **travail à faire** côté coop :

  | Événement | Le mail dit… |
  |---|---|
  | `withdrawal.admin_pending` | Un membre a demandé un **retrait**, il attend une décision (valider/rejeter). |
  | `loan.credit_dossier_ready` | Un **dossier de crédit** est passé en instruction, le comité doit l'examiner. |

Pourquoi un réglage séparé : le système connaît l'adresse d'un membre, mais pas
celle de « l'équipe » — il faut la lui déclarer.

- **Champ vide** → ces 2 alertes internes ne partent nulle part. Le
  retrait/dossier apparaît quand même dans le back-office (l'équipe le voit en se
  connectant), mais **personne n'est prévenu par mail**.
- **Champ renseigné** → un mail atterrit dans la boîte de l'équipe dès qu'une
  action est en attente → réactivité.

**Pas bloquant** (rien n'est cassé sans), mais pratique pour ne pas surveiller le
back-office en permanence. Laissable vide si l'équipe gère tout via l'admin.

### Comment le renseigner

`seed_app_settings` **ne remplit jamais** cette valeur (il garde l'existant) → à
faire à la main, une seule fois.

Option A — en ligne de commande (remplace par ta vraie adresse) :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from apps_coop.audit.models import AppSetting; \
AppSetting.objects.update_or_create(cle='notifications.ops_email', defaults={'valeur':'ops@gathe-finance.com'}); \
print('ops_email =', AppSetting.objects.get(cle='notifications.ops_email').valeur)"

# Optionnel — lien admin dans les mails staff :
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from apps_coop.audit.models import AppSetting; \
AppSetting.objects.update_or_create(cle='notifications.admin_url', defaults={'valeur':'https://admin.gathe-finance.horus-lab.com'})"
```

Option B — back-office admin → Paramètres système :

- **`notifications.ops_email`** = e-mail de l'équipe (ex. `ops@gathe-finance.com`)
- **`notifications.admin_url`** *(optionnel)* = `https://admin.gathe-finance.horus-lab.com`

---

## 3. Vérifier

```bash
# Les 6 nouveaux events sont enregistrés ?
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from apps_coop.notifications.models import EventConfig; \
print(EventConfig.objects.filter(code__in=[ \
'loan.closed','lender.tranche_released','lender.apport_restitution', \
'withdrawal.admin_pending','loan.credit_dossier_ready','loan.avaliste_gel_released' \
]).count())"
# → doit afficher 6

# L'adresse ops est bien renseignée ?
docker compose -f infra/docker-compose.prod.yml exec backend \
  python manage.py shell -c "from apps_coop.audit.services import get_str_setting; \
print(repr(get_str_setting('notifications.ops_email','')))"
```

---

## E-mails concernés (récap)

| Destinataire | Événement | Déclenchement |
|---|---|---|
| Membre | `withdrawal.requested` | Demande de retrait (accusé de réception) |
| **Équipe (ops)** | `withdrawal.admin_pending` | Un retrait attend une décision |
| **Équipe (ops)** | `loan.credit_dossier_ready` | Un dossier crédit passe en instruction comité |
| Membre | `loan.closed` | Crédit intégralement remboursé (soldé) |
| Garant | `loan.avaliste_gel_released` | Caution avaliste libérée (rejet / clôture) |
| Prêteur | `lender.tranche_released` | Part de placement libérée à la clôture du crédit |
| Prêteur | `lender.apport_restitution` | Placement restitué par apport (anticipé, admin) |
