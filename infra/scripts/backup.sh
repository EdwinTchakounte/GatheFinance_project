#!/bin/sh
# pg_dump quotidien → /backups/gathe-YYYY-MM-DD.sql.gz + nettoyage > BACKUP_RETENTION_DAYS jours.
# Lancé par cron dans le conteneur `backup` (cf. docker-compose.prod.yml).

set -eu

TODAY=$(date +%Y-%m-%d)
OUT="/backups/gathe-${TODAY}.sql.gz"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"

echo "[$(date -Iseconds)] backup → ${OUT}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  -h "${POSTGRES_HOST:-db}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --no-owner --no-privileges \
  | gzip > "${OUT}"

# Pruning des dumps anciens
find /backups -type f -name "gathe-*.sql.gz" -mtime "+${RETENTION}" -delete

echo "[$(date -Iseconds)] backup done. Files :"
ls -lh /backups | tail -20
