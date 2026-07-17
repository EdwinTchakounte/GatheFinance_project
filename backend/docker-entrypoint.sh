#!/usr/bin/env bash
set -e

# Wait for the database to accept connections (when DATABASE_URL points at one).
if [ -n "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] waiting for database..."
  python - <<'PY'
import os, sys, time
import django
django.setup()
from django.db import connections
from django.db.utils import OperationalError
for _ in range(60):
    try:
        connections["default"].cursor()
        print("[entrypoint] database is up")
        break
    except OperationalError:
        time.sleep(1)
else:
    print("[entrypoint] database did not become available", file=sys.stderr)
    sys.exit(1)
PY
fi

echo "[entrypoint] applying migrations..."
python manage.py migrate --noinput

if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  echo "[entrypoint] collecting static files..."
  python manage.py collectstatic --noinput
fi

echo "[entrypoint] bootstrapping site content (idempotent)..."
python manage.py bootstrap_site || true
python manage.py seed_blog || true
python manage.py seed_fees || true
python manage.py seed_rates || true
# Planification des crons django-q2 (suspension annuelle, interets mensuels,
# expiration funding 24h, reconciliation paiements...). SANS ce seed, le worker
# qcluster tourne mais n'a AUCUNE tache planifiee a executer. Idempotent
# (get_or_create par nom) : sans effet si les schedules existent deja. Le
# service qcluster demarre apres le backend (depends_on healthy), donc pas de
# course sur la creation des Schedule.
python manage.py seed_q_schedules || true

# Create an admin user from env vars (Django reads DJANGO_SUPERUSER_PASSWORD itself).
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --noinput \
    --username "${DJANGO_SUPERUSER_USERNAME}" \
    --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" >/dev/null 2>&1 \
    && echo "[entrypoint] superuser '${DJANGO_SUPERUSER_USERNAME}' created" \
    || echo "[entrypoint] superuser already exists (or creation skipped)"
fi

echo "[entrypoint] starting: $*"
exec "$@"
