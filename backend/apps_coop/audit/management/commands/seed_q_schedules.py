"""Idempotent seed of the 3 django-q2 cron schedules.

Run after each deploy with ``python manage.py seed_q_schedules``. Safe to
re-run — only creates missing schedules, never overwrites an admin-edited one.

The cluster is started with ``python manage.py qcluster`` (or as a separate
service in docker compose). Without that worker, schedules just sit in the DB.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django_q.models import Schedule


SCHEDULES = [
    {
        "name": "savings.interest.monthly",
        "func": "apps_coop.savings.tasks.crediter_interets_mensuels",
        "schedule_type": Schedule.CRON,
        "cron": "0 2 1 * *",  # 1er du mois à 02:00 (Africa/Douala)
        "description": "Crédit des intérêts d'épargne (configurable via AppSetting savings.interest.*)",
    },
    {
        "name": "loans.overdue.daily",
        "func": "apps_coop.loans.tasks.suivi_retards_quotidien",
        "schedule_type": Schedule.CRON,
        "cron": "0 3 * * *",  # tous les jours à 03:00
        "description": "Détection des échéances de crédit en retard + relances graduées",
    },
    {
        "name": "payments.reconcile.hourly",
        "func": "apps_coop.payments.tasks.reconcile_pending_payments_scheduled",
        "schedule_type": Schedule.CRON,
        "cron": "0 * * * *",  # toutes les heures pile
        "description": "Filet de sécurité webhook Tara — interroge Tara pour les Payments en_attente > 30 min",
    },
]


class Command(BaseCommand):
    help = "Seed the 3 django-q2 cron schedules (idempotent)."

    def handle(self, *args, **options):
        created = 0
        existed = 0
        for spec in SCHEDULES:
            obj, was_created = Schedule.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "func": spec["func"],
                    "schedule_type": spec["schedule_type"],
                    "cron": spec["cron"],
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {obj.name}  ({spec['cron']})"))
                self.stdout.write(f"      → {spec['description']}")
            else:
                existed += 1
                self.stdout.write(f"  · {obj.name} (déjà présent)")
        self.stdout.write(self.style.SUCCESS(f"\n{created} créé(s), {existed} déjà en base."))
        self.stdout.write("Démarrer le worker : python manage.py qcluster")
