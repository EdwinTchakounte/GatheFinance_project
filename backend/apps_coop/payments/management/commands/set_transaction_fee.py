"""Pose le frais de transaction sur versement (taux + périmètre) — admin/ops.

Contrairement à ``seed_fees`` (idempotent, n'écrase jamais), cette commande
FIXE explicitement la valeur : elle sert à appliquer un réglage voulu (ex. 3 %
sur le versement seul) sans passer par l'UI, ou à corriger une valeur héritée.

Exemples :
    python manage.py set_transaction_fee                      # 3 % sur versement
    python manage.py set_transaction_fee --rate 0.03 --operations versement
    python manage.py set_transaction_fee --rate 0.05 --operations versement,retrait
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError

from apps_coop.audit.models import AppSetting
from apps_coop.payments.fee_policy import ALL_OPERATIONS, SETTING_KEY
from apps_coop.payments.models import RateParam


class Command(BaseCommand):
    help = (
        "Fixe le taux de frais de transaction sur versement et son périmètre. "
        "Défaut : 3 % sur le versement seul."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--rate",
            default="0.03",
            help="Taux décimal (0.03 = 3 %). Défaut 0.03.",
        )
        parser.add_argument(
            "--operations",
            default="versement",
            help=(
                "Périmètre CSV parmi versement,retrait,transfert. "
                "Défaut « versement »."
            ),
        )

    def handle(self, *args, **options):
        try:
            rate = Decimal(str(options["rate"]))
        except (InvalidOperation, TypeError) as exc:
            raise CommandError(f"Taux invalide : {options['rate']!r}") from exc
        if rate < 0:
            raise CommandError("Le taux ne peut pas être négatif.")

        ops_raw = [o.strip().lower() for o in str(options["operations"]).split(",")]
        ops = [o for o in ops_raw if o in ALL_OPERATIONS]
        if not ops:
            raise CommandError(
                f"Périmètre invalide : {options['operations']!r} "
                f"(valeurs possibles : {', '.join(ALL_OPERATIONS)})."
            )
        ops_csv = ",".join(ops)

        RateParam.objects.update_or_create(
            code=RateParam.Code.TRANSACTION_FEE,
            defaults={
                "libelle": "Frais de transaction sur versement (%)",
                "valeur": rate,
                "actif": True,
            },
        )
        AppSetting.objects.update_or_create(
            cle=SETTING_KEY, defaults={"valeur": ops_csv}
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Frais de transaction fixé : {rate} "
                f"({(rate * 100):.2f} %) sur [{ops_csv}]."
            )
        )
