"""Archive les AuditLog plus vieux que N jours dans un fichier TXT gzippe.

Run : python manage.py archive_audit_logs [--days 3] [--dry-run]

Objectif : eviter que la table AuditLog grossisse indefiniment en prod.
Tous les 3 jours (cron), on exporte les entrees > 3 jours vers un fichier
texte horodate dans MEDIA_ROOT/coop/logs_archive/, puis on supprime les
enregistrements archives.

Format du fichier : un JSON Line par entree (ligne = json.dumps de la
row), compresse en .txt.gz pour minimiser l'empreinte disque tout en
restant lisible avec `zcat`.

Idempotent : si le fichier du jour existe deja, append en mode 'ab'.
Defensif : ne supprime de la BD que les rows reellement ecrites dans le
fichier (commit Django) . jamais de perte de donnees.

Cron tag : LOGS_ARCHIVE_3D (declenche par django_q toutes les 3 jours).
"""
from __future__ import annotations

import gzip
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.models import AuditLog


class Command(BaseCommand):
    help = (
        "Archive les AuditLog plus vieux que N jours dans un .txt.gz "
        "puis supprime les enregistrements de la BD."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=3,
            help="Anciennete minimum d'une entree pour etre archivee (defaut: 3).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche le plan sans rien ecrire ni supprimer.",
        )

    def handle(self, *args, **options):
        days = int(options["days"])
        dry = bool(options["dry_run"])

        cutoff = timezone.now() - timedelta(days=days)
        qs = AuditLog.objects.filter(created_at__lt=cutoff).order_by("created_at")
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f"Rien a archiver (cutoff = {cutoff.isoformat()})."
            ))
            return

        archive_dir = Path(settings.MEDIA_ROOT) / "coop" / "logs_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        today = timezone.localdate().isoformat()
        out_path = archive_dir / f"audit_{today}.txt.gz"

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Archivage de {total} entrees -> {out_path}"
        ))
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN : aucun fichier ecrit."))
            for log in qs[:5]:
                self.stdout.write(f"  preview : {log.created_at.isoformat()} {log.action}")
            return

        archived = 0
        # Ouverture en mode append-binaire pour permettre les reruns du
        # meme jour (idempotent au niveau du fichier).
        with gzip.open(out_path, "ab") as gz:
            with transaction.atomic():
                batch_ids: list[int] = []
                for log in qs.iterator(chunk_size=1000):
                    row = {
                        "id": log.id,
                        "created_at": log.created_at.isoformat(),
                        "user_id": log.user_id,
                        "action": log.action,
                        "entite_type": log.entite_type,
                        "entite_id": log.entite_id,
                        "details": log.details_json,
                        "ip": log.ip,
                        "user_agent": log.user_agent,
                    }
                    line = json.dumps(row, ensure_ascii=False) + "\n"
                    gz.write(line.encode("utf-8"))
                    batch_ids.append(log.id)
                    archived += 1
                    if len(batch_ids) >= 1000:
                        AuditLog.objects.filter(id__in=batch_ids).delete()
                        batch_ids.clear()
                if batch_ids:
                    AuditLog.objects.filter(id__in=batch_ids).delete()

        size_kb = out_path.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(
            f"OK . {archived} entrees archivees ({size_kb} KB) -> {out_path}"
        ))
