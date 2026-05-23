"""Seed des RateParam selon le Règlement Intérieur 2025.

Idempotent : crée les codes manquants à leur valeur réglementaire et ne touche
JAMAIS une ligne déjà éditée par l'admin (les taux sont modifiables).

Valeurs réglementaires (ratios) :
    - LOAN_INTEREST             : 0.10  (10 % par transaction, Article 5)
    - SAVINGS_INTEREST_MONTHLY  : 0.01  (1 % / mois, Article 4)
    - RENEWAL_CASH              : 0.10  (intérêts au comptant, Article 11)
    - RENEWAL_DEFERRED          : 0.15  (intérêts reportés, Article 11)
    - LATE_PENALTY              : 0.50  (pénalité non-versement, Article 12)

Les défauts sont lus depuis ``payments.rates`` (source = terms.py / cutoff.py)
pour qu'il n'existe qu'une seule source de vérité numérique.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.payments.models import RateParam
from apps_coop.payments.rates import default_rate


# Libellés (la valeur vient de default_rate → terms.py / cutoff.py).
RATE_LABELS: dict[str, str] = {
    RateParam.Code.LOAN_INTEREST: "Taux d'intérêt crédit (par transaction)",
    RateParam.Code.SAVINGS_INTEREST_MONTHLY: "Taux d'intérêt épargne (mensuel)",
    RateParam.Code.RENEWAL_CASH: "Reconduction — intérêts au comptant",
    RateParam.Code.RENEWAL_DEFERRED: "Reconduction — intérêts reportés",
    RateParam.Code.LATE_PENALTY: "Pénalité de non-versement",
}


class Command(BaseCommand):
    help = (
        "Crée les RateParam manquants à leur valeur réglementaire "
        "(crédit 10 %, épargne 1 %, reconduction 10/15 %, pénalité 50 %). "
        "Idempotent : ne réécrit jamais une valeur déjà éditée par l'admin."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        for code, libelle in RATE_LABELS.items():
            valeur = default_rate(code)
            rate, was_created = RateParam.objects.get_or_create(
                code=code,
                defaults={"libelle": libelle, "valeur": valeur, "actif": True},
            )
            if was_created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created  {code:<26} → {valeur}")
                )
            else:
                self.stdout.write(
                    f"  · Kept     {code:<26} → {rate.valeur} (admin-edited)"
                )
        self.stdout.write(self.style.SUCCESS("Seed rates done."))
