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
        "description": (
            "LEGACY 2025 — Crédit des intérêts d'épargne. Désactivé par défaut "
            "depuis la refonte 2026 (kill-switch savings.monthly_interest.enabled)."
        ),
    },
    {
        "name": "collecte.fin_de_mois",
        "func": "apps_coop.savings.tasks.collecte_fin_de_mois",
        "schedule_type": Schedule.CRON,
        "cron": "0 2 1 * *",  # 1er du mois à 02:00 — clôture mensuelle.
        "description": (
            "REFONTE 2026 (LOT 4) — Clôture mensuelle des comptes de collecte "
            "journalière : commission 1% configurable + restitution cash OU "
            "bascule vers épargne classique selon end_of_month_preference."
        ),
    },
    {
        "name": "collecte.eom_choice_reminder",
        "func": "apps_coop.savings.tasks.collecte_eom_choice_reminder",
        "schedule_type": Schedule.CRON,
        "cron": "0 9 25 * *",  # le 25 à 09:00 — rappel avant la clôture du 1er.
        "description": (
            "REFONTE 2026 — Rappel mensuel (notification éditable) invitant les "
            "membres avec un solde de collecte à choisir cash vs bascule épargne "
            "avant la clôture. Tunable collecte.eom_reminder.enabled."
        ),
    },
    {
        "name": "placement.maturity.daily",
        "func": "apps_coop.savings.tasks.placement_maturity_processing",
        "schedule_type": Schedule.CRON,
        "cron": "0 4 * * *",  # quotidien 04:00 — n'agit qu'au jour d'échéance.
        "description": (
            "REFONTE 2026 — Restitution des placements à la date d'échéance "
            "éditable (epargne.placement.maturity_date, défaut 01-01) : intérêts "
            "prorata crédités + tranches DISPONIBLE libérées."
        ),
    },
    {
        "name": "epargne.anniversary.daily",
        "func": "apps_coop.savings.tasks.epargne_anniversary_processing",
        "schedule_type": Schedule.CRON,
        "cron": "30 3 * * *",  # tous les jours à 03:30 (Africa/Douala).
        "description": (
            "REFONTE 2026 (LOT 5) — Pilote la state machine des comptes "
            "d'épargne classique autour de la maturité 12 mois : NOTIFIE → "
            "URGENCE → restitution + EN_ATTENTE_PAIEMENT → ARCHIVE après grace."
        ),
    },
    {
        "name": "loans.overdue.daily",
        "func": "apps_coop.loans.tasks.suivi_retards_quotidien",
        "schedule_type": Schedule.CRON,
        "cron": "0 3 * * *",  # tous les jours à 03:00
        "description": "Détection des échéances de crédit en retard + relances graduées",
    },
    {
        "name": "loans.due_soon.daily",
        "func": "apps_coop.loans.tasks.rappel_echeances_proches",
        "schedule_type": Schedule.CRON,
        "cron": "0 8 * * *",  # tous les jours à 08:00
        "description": "Rappel proactif J-3 des échéances de crédit à venir",
    },
    {
        "name": "payments.reconcile.hourly",
        "func": "apps_coop.payments.tasks.reconcile_pending_payments_scheduled",
        "schedule_type": Schedule.CRON,
        # O1 . cron passe a 15 min apres recette STK (etait */5 phase test).
        # Reduit la charge API Tara . le webhook reste le canal principal,
        # ce cron est le filet de securite.
        "cron": "*/15 * * * *",
        "description": "Filet de sécurité webhook Tara — interroge Tara pour les Payments en_attente > 2 min (toutes les 15 min)",
    },
    {
        # O5 . Alerte admin si paiements bloques > 60 min (tunable via
        # AppSetting payments.alert.stuck_after_minutes). Email envoye aux
        # destinataires de payments.alert.recipients (csv).
        "name": "payments.alert.stuck",
        "func": "apps_coop.payments.tasks.alert_stuck_payments",
        "schedule_type": Schedule.CRON,
        "cron": "0 * * * *",  # toutes les heures pile.
        "description": "Notifie les admins par mail si des Payments restent EN_ATTENTE > 60 min (panne Tara silencieuse ou worker arrete)",
    },
    {
        "name": "members.reinscription.daily",
        "func": "apps_coop.members.tasks.rappel_reinscription_annuelle",
        "schedule_type": Schedule.CRON,
        "cron": "0 9 * * *",  # tous les jours à 09:00 (Africa/Douala)
        "description": "A2 — Alerte douce J-N avant l'anniversaire annuel d'adhésion",
    },
    {
        "name": "loans.funding.window_expiry",
        "func": "apps_coop.loans.tasks.funding_window_expiry_task",
        "schedule_type": Schedule.CRON,
        "cron": "*/15 * * * *",  # toutes les 15 minutes
        "description": (
            "REFONTE 2026 (LOT 8) — Funding 24h : pose AUTO_ACCEPTED sur les "
            "LenderConsentRequest dont la deadline est écoulée, puis finalise "
            "(FUNDED) ou réalloue (REALLOCATING / EN_ATTENTE_FUNDING) les "
            "LoanFundingRequest dont la vague est entièrement traitée."
        ),
    },
    {
        "name": "loans.microcampaign.close_expired",
        "func": "apps_coop.loans.tasks.microcampaign_close_expired_task",
        "schedule_type": Schedule.CRON,
        "cron": "15 4 * * *",  # tous les jours à 04:15 (Africa/Douala).
        "description": (
            "REFONTE 2026 (LOT 11) — Clôture des micro-campagnes dont la "
            "date_fin est passée (pose actif=False + closed_at + audit). "
            "Idempotent."
        ),
    },
    {
        "name": "loans.judicial.auto_escalate",
        "func": "apps_coop.loans.tasks.judicial_auto_escalation_task",
        "schedule_type": Schedule.CRON,
        "cron": "0 5 * * *",  # tous les jours à 05:00 (Africa/Douala).
        "description": (
            "REFONTE 2026 (LOT 14) — Escalade judiciaire automatique. No-op "
            "si loans.judicial_escalation.mode == 'manual'. Sinon, ouvre une "
            "JudicialEscalation pour chaque Loan dont poursuite_judiciaire_at "
            "est dépassée de loans.judicial_escalation.delay_days jours."
        ),
    },
    {
        "name": "ecritures.backup.daily",
        "func": "django.core.management.call_command",
        "args": "'backup_ecritures'",
        "schedule_type": Schedule.CRON,
        "cron": "0 22 * * *",  # tous les jours à 22:00 (Africa/Douala).
        "description": (
            "Sauvegarde quotidienne des ECRITURES (Payment + registres épargne "
            "collecte/classique + remboursements/échéances/intérêts prêteur) → "
            "MEDIA_ROOT/coop/backups/ecritures_YYYY-MM-DD.jsonl.gz. Non "
            "destructif, rétention 90 j. Complète le dump SGBD (service backup, 03h)."
        ),
    },
    {
        "name": "audit.archive_logs_3d",
        "func": "django.core.management.call_command",
        "args": "'archive_audit_logs'",
        "kwargs": {"days": 3},
        "schedule_type": Schedule.CRON,
        "cron": "30 2 */3 * *",  # tous les 3 jours à 02:30 (Africa/Douala).
        "description": (
            "Archivage AuditLog → fichier TXT gzippé dans "
            "MEDIA_ROOT/coop/logs_archive/audit_YYYY-MM-DD.txt.gz, "
            "puis suppression des entrées > 3 jours pour libérer la BD. "
            "Idempotent : append-mode si fichier du jour existe."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the 3 django-q2 cron schedules (idempotent)."

    def handle(self, *args, **options):
        created = 0
        existed = 0
        for spec in SCHEDULES:
            defaults = {
                "func": spec["func"],
                "schedule_type": spec["schedule_type"],
                "cron": spec["cron"],
            }
            if "args" in spec:
                defaults["args"] = spec["args"]
            if "kwargs" in spec:
                # django_q.Schedule.kwargs est une str repr() d'un dict.
                defaults["kwargs"] = repr(spec["kwargs"])
            obj, was_created = Schedule.objects.get_or_create(
                name=spec["name"],
                defaults=defaults,
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
