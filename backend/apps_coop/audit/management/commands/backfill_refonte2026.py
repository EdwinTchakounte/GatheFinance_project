"""LOT 3 (refonte 2026) — Audit/backfill manuel des données existantes.

Complète la migration de données ``savings.0006_backfill_lot2_maturity`` :
permet à un admin de **re-vérifier l'état** ou de **rattraper** des cas
limites en prod sans nouvelle migration (ex. un compte créé entre la migration
et le déploiement effectif).

Usage :

    # Audit (lit, n'écrit rien) — recommandé en premier.
    python manage.py backfill_refonte2026 --dry-run

    # Application réelle.
    python manage.py backfill_refonte2026

Idempotent : ne touche QUE les comptes avec ``date_prochaine_maturite IS NULL``.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction


def _add_months(d: date, months: int) -> date:
    total_months = (d.year * 12 + d.month - 1) + months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    last_day = monthrange(new_year, new_month)[1]
    return d.replace(year=new_year, month=new_month, day=min(d.day, last_day))


class Command(BaseCommand):
    help = (
        "LOT 3 — Audit et backfill des comptes d'épargne classique sans "
        "``date_prochaine_maturite`` (refonte 2026). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait changé sans rien écrire en base.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from apps_coop.audit.services import get_int_setting
        from apps_coop.savings.models import ClassicSavingsAccount

        dry_run = bool(options.get("dry_run"))
        contract_months = get_int_setting("epargne.contract_months", 12)

        qs = ClassicSavingsAccount.objects.filter(
            date_prochaine_maturite__isnull=True
        ).select_related("member")

        total_null = qs.count()
        self.stdout.write(
            self.style.WARNING(
                f"{total_null} compte(s) sans date_prochaine_maturite "
                f"(contract_months={contract_months})."
            )
        )

        if total_null == 0:
            self.stdout.write(self.style.SUCCESS("Rien à faire — tout est à jour."))
            return

        applied = 0
        for account in qs.iterator():
            target = _add_months(account.date_ouverture, contract_months)
            self.stdout.write(
                f"  · {account.member.numero_membre} · "
                f"ouvert {account.date_ouverture} → maturité {target}"
            )
            if not dry_run:
                account.date_prochaine_maturite = target
                account.save(update_fields=["date_prochaine_maturite"])
            applied += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[DRY-RUN] {applied} compte(s) seraient mis à jour."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n{applied} compte(s) mis à jour.")
            )
