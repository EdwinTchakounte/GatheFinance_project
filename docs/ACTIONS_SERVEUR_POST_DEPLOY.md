# Actions serveur — à exécuter au déploiement

> Checklist des commandes/manips **manuelles** requises côté serveur après un
> déploiement, pour que le code livré fonctionne pleinement. Les **migrations
> sont appliquées automatiquement** par l'entrypoint backend (`docker-entrypoint.sh`
> lance `migrate` avant de servir) — rien à faire pour elles.
>
> Contexte : chantier de vérifications de pré-livraison 2026-07-21 (cf.
> `docs/audits/Audit-Pre-Livraison-Gathe-Finance.pdf`).

Les commandes s'exécutent dans le conteneur backend, ex. :

```bash
docker compose -f infra/docker-compose.prod.yml exec backend python manage.py <cmd>
```

---

## 1. Notifications avaliste + staff (audit §5)

Deux nouveaux e-mails ont été ajoutés : **« dossier crédit prêt »** (à l'équipe)
et **« caution avaliste libérée »** (au garant). Ils **ne partiront pas** tant que
les catalogues d'événements et les templates ne sont pas re-semés, et tant que
l'adresse ops n'est pas renseignée. Le code **ne plante pas** sans ça (no-op).

```bash
python manage.py seed_event_catalog        # + avaliste_gel_released, credit_dossier_ready, loan.closed, lender.tranche_released, lender.apport_restitution, withdrawal.admin_pending
python manage.py seed_email_templates --force   # + les templates correspondants
python manage.py seed_app_settings          # + notifications.ops_email, notifications.admin_url
```

> Événements e-mail ajoutés (re-semer pour qu'ils partent) : **caution avaliste
> libérée** (au garant), **dossier crédit prêt** (à l'équipe ops), **crédit soldé**
> (au membre, à la clôture), **part de placement libérée** (au prêteur, à la
> clôture du crédit financé), **placement restitué par apport** (au prêteur,
> restitution anticipée décidée par l'admin), **retrait à traiter** (à l'équipe ops, à chaque demande de retrait).
>
> Les **migrations** (`Member.photo_profil`, `LenderAllocation.restitue_par_apport`,
> etc.) sont appliquées automatiquement par l'entrypoint — rien à faire.

Puis, dans le back-office (réglages / AppSettings), **renseigner** :

- `notifications.ops_email` → l'adresse e-mail de l'équipe qui doit recevoir
  l'alerte « un dossier crédit est prêt pour le comité ». **Vide = aucune alerte
  staff** (le reste du flux marche quand même : file + badge KPI).
- `notifications.admin_url` *(optionnel)* → URL publique du back-office admin
  (pour le lien dans l'e-mail staff). Vide = repli sur l'URL du portail membre.

> `seed_email_templates --force` re-provisionne aussi le template **welcome**
> (e-mail de bienvenue) et tous les autres — sans risque, idempotent.

---

## 2. (Rappel) Clé API e-mail

L'envoi d'e-mails passe par l'API HTTP Brevo. La **clé API** doit être posée sur
le serveur (variable d'environnement / secret). Sans elle, les e-mails ci-dessus
sont journalisés en échec mais ne partent pas.

---

## Vérification rapide après exécution

```bash
# Les 2 nouveaux events sont bien enregistrés :
python manage.py shell -c "from apps_coop.notifications.models import EventConfig; \
print(EventConfig.objects.filter(code__in=['loan.avaliste_gel_released','loan.credit_dossier_ready']).count())"
# → doit afficher 2

# L'adresse ops est renseignée :
python manage.py shell -c "from apps_coop.audit.services import get_str_setting; \
print(repr(get_str_setting('notifications.ops_email','')))"
```
