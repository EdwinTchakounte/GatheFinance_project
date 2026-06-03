"""Seed des paliers de durée (Article 7) et modalités (Article 8) — EXT-2.

Idempotent : crée les lignes manquantes à leur valeur réglementaire et ne
touche JAMAIS une ligne déjà éditée par l'admin (montant, durée, actif).

Les défauts proviennent de ``loans/terms.py`` (source de vérité réglementaire)
pour qu'il n'existe qu'une seule liste hardcodée.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.loans.models import LoanDurationTier, PaymentModalityConfig
from apps_coop.loans.terms import LOAN_DURATION_TIERS, PaymentModality


class Command(BaseCommand):
    help = (
        "Seed les paliers Art.7 (montant→durée) et les modalités Art.8 "
        "(journalier/hebdo/mensuel). Idempotent."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created_tiers = self._seed_tiers()
        created_modalities = self._seed_modalities()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created_tiers} palier(s) + {created_modalities} modalité(s) créé(s)."
            )
        )

    def _seed_tiers(self) -> int:
        created = 0
        for index, (lo, hi, months) in enumerate(LOAN_DURATION_TIERS, start=1):
            # Idempotence par montant_min (clé naturelle).
            obj, was_created = LoanDurationTier.objects.get_or_create(
                montant_min=lo,
                defaults={
                    "montant_max": hi,
                    "duree_mois": months,
                    "ordering": index,
                    "actif": True,
                },
            )
            if was_created:
                created += 1
                hi_str = f"{hi}" if hi is not None else "∞"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Palier  [{lo:>9} – {hi_str:>9}] → {months} mois"
                    )
                )
            else:
                self.stdout.write(
                    f"  · Palier  [{lo} – …] (déjà en base — non modifié)"
                )
        return created

    def _seed_modalities(self) -> int:
        created = 0
        for index, (code, libelle) in enumerate(PaymentModality.CHOICES, start=1):
            per_month = PaymentModality.INSTALLMENTS_PER_MONTH[code]
            obj, was_created = PaymentModalityConfig.objects.get_or_create(
                code=code,
                defaults={
                    "libelle": libelle,
                    "installments_per_month": per_month,
                    "ordering": index,
                    "actif": True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Modalité  {libelle:<14} ({per_month}/mois)"
                    )
                )
            else:
                self.stdout.write(
                    f"  · Modalité  {libelle} (déjà en base — non modifiée)"
                )
        return created
