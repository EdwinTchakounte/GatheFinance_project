"""EXT-2 — Paliers Art.7 et modalités Art.8 modifiables sans déploiement.

Prouve qu'un admin peut :
  - ajouter / désactiver un palier de durée → ``duration_months_for`` lit la DB
  - ajuster la cadence d'une modalité → ``n_installments`` lit la DB
  - retomber sur le défaut Règlement si la table est vide
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps_coop.loans.models import LoanDurationTier, PaymentModalityConfig
from apps_coop.loans.terms import (
    LOAN_DURATION_TIERS,
    PaymentModality,
    duration_months_for,
    n_installments,
)


pytestmark = pytest.mark.django_db


class TestDurationTiersTunable:
    """Article 7 — paliers (montant → durée) pilotables depuis la DB."""

    def test_falls_back_to_regulation_when_table_empty(self):
        # Table vide → on lit les paliers du code (LOAN_DURATION_TIERS).
        assert LoanDurationTier.objects.count() == 0
        # 100 000 FCFA tombe dans le palier [51 000 – 200 000] → 3 mois.
        assert duration_months_for(Decimal("100000")) == 3

    def test_db_tiers_override_regulation(self):
        # L'admin redéfinit complètement les paliers — un seul palier ouvert
        # de 5 000 à +∞, durée fixe de 12 mois.
        LoanDurationTier.objects.create(
            montant_min=Decimal("5000"),
            montant_max=None,
            duree_mois=12,
            actif=True,
            ordering=1,
        )
        # 100 000 doit maintenant rendre 12 mois (et pas les 3 du Règlement).
        assert duration_months_for(Decimal("100000")) == 12

    def test_disabling_middle_tier_falls_back_to_next_tier(self):
        # On seede les 8 paliers Règlement.
        for i, (lo, hi, months) in enumerate(LOAN_DURATION_TIERS, start=1):
            LoanDurationTier.objects.create(
                montant_min=lo, montant_max=hi, duree_mois=months,
                actif=True, ordering=i,
            )
        # Sanity : 300 000 = palier 3 [201 000 – 350 000] → 4 mois.
        assert duration_months_for(Decimal("300000")) == 4

        # L'admin désactive le palier 3 (la tranche 201 000–350 000 disparaît).
        # Un montant de 300 000 doit tomber sur le palier suivant actif
        # [351 000 – 500 000] → 5 mois (durée plus longue, sécurise le membre).
        tier3 = LoanDurationTier.objects.get(montant_min=Decimal("201000"))
        tier3.actif = False
        tier3.save()
        assert duration_months_for(Decimal("300000")) == 5

    def test_disabling_first_tier_raises_floor(self):
        # Désactiver le palier d'entrée = remonter le plancher de crédit.
        # Comportement souhaité : on refuse les montants sous le nouveau seuil.
        for i, (lo, hi, months) in enumerate(LOAN_DURATION_TIERS, start=1):
            LoanDurationTier.objects.create(
                montant_min=lo, montant_max=hi, duree_mois=months,
                actif=True, ordering=i,
            )
        first = LoanDurationTier.objects.order_by("ordering").first()
        first.actif = False
        first.save()
        # 30 000 (sous 51 000) → refusé : pas de palier d'entrée actif.
        with pytest.raises(ValueError, match="inférieur au minimum"):
            duration_months_for(Decimal("30000"))

    def test_min_amount_validation_uses_db_tiers(self):
        # Admin remonte le plancher à 10 000.
        LoanDurationTier.objects.create(
            montant_min=Decimal("10000"),
            montant_max=Decimal("100000"),
            duree_mois=3,
            actif=True,
            ordering=1,
        )
        # 5 000 < 10 000 → erreur.
        with pytest.raises(ValueError, match="inférieur au minimum"):
            duration_months_for(Decimal("5000"))
        # 15 000 → OK, 3 mois.
        assert duration_months_for(Decimal("15000")) == 3


class TestPaymentModalitiesTunable:
    """Article 8 — cadence (échéances par mois) pilotable depuis la DB."""

    def test_falls_back_to_regulation_when_table_empty(self):
        assert PaymentModalityConfig.objects.count() == 0
        # Défaut Règlement : journalier = 30 / mois, durée 2 mois → 60 échéances.
        assert n_installments(2, PaymentModality.JOURNALIER) == 60

    def test_db_modality_overrides_regulation(self):
        # L'admin redéfinit le journalier à 22 (jours ouvrés/mois plutôt
        # que 30 jours calendaires).
        PaymentModalityConfig.objects.create(
            code=PaymentModality.JOURNALIER,
            libelle="Journalier",
            installments_per_month=22,
            actif=True,
            ordering=1,
        )
        assert n_installments(2, PaymentModality.JOURNALIER) == 44

    def test_disabled_modality_falls_back_to_regulation(self):
        # Modalité présente mais désactivée → on retombe sur la cadence Règlement.
        PaymentModalityConfig.objects.create(
            code=PaymentModality.MENSUEL,
            libelle="Mensuel",
            installments_per_month=99,  # valeur farfelue
            actif=False,                # désactivée
            ordering=1,
        )
        # Comme la ligne est inactive, fallback Règlement → 1/mois.
        assert n_installments(3, PaymentModality.MENSUEL) == 3
