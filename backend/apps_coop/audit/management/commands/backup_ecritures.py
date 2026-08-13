"""Backup quotidien des ECRITURES (mouvements comptables) → JSONL gzippe.

Run : python manage.py backup_ecritures [--retention 90] [--dry-run]

Objectif : disposer chaque jour d'un instantane exportable de toutes les
ecritures financieres de la cooperative, independamment du dump SGBD complet
(service `backup`, pg_dump a 03h). Ici on cible specifiquement les tables
« registre » (append-only) qui portent la comptabilite reelle :

    - payments.Payment                 (pivot de TOUT mouvement d'argent)
    - savings.SavingsTransaction       (registre collecte journaliere)
    - savings.ClassicSavingsTransaction(registre epargne classique)
    - loans.LoanRepayment              (remboursements de credit)
    - loans.LoanInstallment            (echeancier)
    - loans.LenderInterestPayout       (reversement interets preteur)

Format : un JSON Line par enregistrement (repr Django `python` serializer →
`{"model": "...", "pk": ..., "fields": {...}}`), compresse en .jsonl.gz.
Robuste au schema (aucun champ code en dur : le serializer suit le modele).

Ecriture NON destructive : contrairement a `archive_audit_logs`, on ne
supprime JAMAIS de lignes en base — c'est une sauvegarde, pas un archivage.

Idempotent : le fichier du jour est reecrit a chaque run (instantane du jour).
Retention : purge des .jsonl.gz plus vieux que --retention jours (defaut 90).

Persistance : ecrit sous MEDIA_ROOT/coop/backups/ (volume `backend_media`,
monte aussi sur le worker qcluster — cf. infra/docker-compose.prod.yml).

Cron tag : ECRITURES_BACKUP_DAILY (django_q, tous les jours a 22:00 Douala).
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand
from django.utils import timezone


# (app_label, model_name) des registres a sauvegarder, dans un ordre stable.
LEDGER_MODELS = [
    ("payments", "Payment"),
    ("savings", "SavingsTransaction"),
    ("savings", "ClassicSavingsTransaction"),
    ("loans", "LoanRepayment"),
    ("loans", "LoanInstallment"),
    ("loans", "LenderInterestPayout"),
]


class Command(BaseCommand):
    help = (
        "Sauvegarde quotidienne des ecritures (Payment + registres epargne + "
        "remboursements/echeances/interets preteur) en .jsonl.gz. Non destructif."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention", type=int, default=90,
            help="Nombre de jours de conservation des backups (defaut: 90).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche le plan (comptes par modele) sans ecrire de fichier.",
        )

    def handle(self, *args, **options):
        retention = int(options["retention"])
        dry = bool(options["dry_run"])

        backup_dir = Path(settings.MEDIA_ROOT) / "coop" / "backups"
        today = timezone.localdate().isoformat()
        out_path = backup_dir / f"ecritures_{today}.jsonl.gz"

        # Recense les modeles disponibles + leur volume (une passe de count).
        planned: list[tuple[str, object, int]] = []
        for app_label, model_name in LEDGER_MODELS:
            try:
                model = apps.get_model(app_label, model_name)
            except LookupError:
                self.stdout.write(self.style.WARNING(
                    f"  ! modele introuvable, ignore : {app_label}.{model_name}"
                ))
                continue
            count = model.objects.count()
            planned.append((f"{app_label}.{model_name}", model, count))

        total = sum(c for _, _, c in planned)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Backup ecritures ({total} lignes, {len(planned)} registres) -> {out_path}"
        ))
        for label, _model, count in planned:
            self.stdout.write(f"  · {label}: {count}")

        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN : aucun fichier ecrit."))
            return

        backup_dir.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        written = 0
        # Mode texte gzip ('wt') : instantane du jour, reecrit a chaque run.
        with gzip.open(out_path, "wt", encoding="utf-8") as fh:
            # En-tete de manifeste (1re ligne) : metadonnees du backup.
            fh.write(json.dumps({
                "_manifest": True,
                "generated_at": timezone.now().isoformat(),
                "date": today,
                "models": [label for label, _m, _c in planned],
                "counts": {label: count for label, _m, count in planned},
            }, ensure_ascii=False) + "\n")

            for label, model, _count in planned:
                qs = model.objects.all().order_by("pk")
                for obj in qs.iterator(chunk_size=1000):
                    # `python` serializer → dict {model, pk, fields}. default=str
                    # gere Decimal/datetime/UUID sans perte.
                    row = serializers.serialize("python", [obj])[0]
                    fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                    written += 1

        size_kb = out_path.stat().st_size // 1024
        elapsed = time.monotonic() - started
        self.stdout.write(self.style.SUCCESS(
            f"OK . {written} ecritures sauvegardees ({size_kb} KB) en {elapsed:.1f}s -> {out_path}"
        ))

        # Purge des backups anterieurs a la fenetre de retention.
        cutoff = time.time() - retention * 86400
        pruned = 0
        for f in backup_dir.glob("ecritures_*.jsonl.gz"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    pruned += 1
            except OSError:
                continue
        if pruned:
            self.stdout.write(self.style.SUCCESS(
                f"Retention {retention}j : {pruned} ancien(s) backup(s) purge(s)."
            ))
