#!/usr/bin/env bash
# =============================================================================
# post-deploy-seed.sh — À lancer 1× APRÈS le tout premier déploiement cliente.
# =============================================================================
# À exécuter SUR le serveur, dans le dossier infra/ (où vit .env.prod) :
#
#   cd /opt/gathe-finance/infra
#   bash scripts/post-deploy-seed.sh
#
# Ce que l'entrypoint backend fait DÉJÀ tout seul à chaque boot (rien à refaire) :
#   migrate, collectstatic, bootstrap_site, seed_blog, seed_fees, seed_rates,
#   seed_q_schedules, createsuperuser.
#
# Ce script complète avec ce qui N'EST PAS automatique :
#   - seed_app_settings          -> pose les AppSettings (dont loans.apport.* : 20%/10%)
#   - seed_email_templates --force -> RÉÉCRIT les gabarits (corrige les liens portail)
#   - notifications.admin_url     -> pointe les liens admin des mails sur admin.<domaine>
#   - re-bootstrap CMS explicite  -> filet si l'entrypoint a avalé une erreur au 1er boot
# Idempotent : relançable sans dcommage.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."   # -> infra/
[ -f .env.prod ] || { echo "!! .env.prod introuvable dans $(pwd). Abandon."; exit 1; }

COMPOSE="docker compose -f docker-compose.prod.yml -f docker-compose.client.yml --env-file .env.prod"
EXEC="$COMPOSE exec -T backend python manage.py"

# Domaine admin lu depuis .env.prod (pour les liens admin dans les emails).
ADMIN_DOMAIN=$(grep -E '^ADMIN_DOMAIN=' .env.prod | cut -d= -f2- | tr -d '"' || true)
ADMIN_URL="https://${ADMIN_DOMAIN:-admin.gathe-finance.com}"

echo ">>> 1/5  AppSettings (seuils, apport 20%/10%, campagnes, ...)"
$EXEC seed_app_settings

echo ">>> 2/5  Gabarits emails (RÉÉCRITURE des liens portail) — seed_email_templates --force"
$EXEC seed_email_templates --force

echo ">>> 3/5  CMS Wagtail (filet idempotent : root/locales/site/blog)"
$EXEC bootstrap_site
$EXEC seed_blog

echo ">>> 4/5  Lien admin des emails -> ${ADMIN_URL}"
$COMPOSE exec -T backend python manage.py shell -c "
from apps_coop.audit.models import AppSetting
AppSetting.objects.update_or_create(
    key='notifications.admin_url',
    defaults={'value': '${ADMIN_URL}'},
)
print('notifications.admin_url =', '${ADMIN_URL}')
" || echo "   (note: modèle AppSetting introuvable sous ce chemin — vérifier si le lien admin est déjà correct)"

echo ">>> 5/5  Contrôle : articles vitrine exposés par l'API CMS ?"
$COMPOSE exec -T backend python manage.py shell -c "
from wagtail.models import Page
n = Page.objects.live().count()
print('pages Wagtail live =', n)
" || true

echo
echo "✅ Post-déploiement terminé. Vérifie ensuite :"
echo "   - https://${ADMIN_DOMAIN:-admin.gathe-finance.com}/  (back-office)"
echo "   - un email de test : les liens ouvrent bien une route portail existante"
echo "   - la vitrine affiche les flyers de campagne (sinon: renseigner MEDIA_DOMAIN dans .env.prod)"
