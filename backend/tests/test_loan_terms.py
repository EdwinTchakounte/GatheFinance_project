"""Tests du moteur de crédit aligné sur le Règlement Intérieur 2025."""
from decimal import Decimal

import pytest

from apps_coop.loans.terms import (
    LOAN_INTEREST_RATE,
    PaymentModality,
    RENEWAL_EXTRA_MONTHS,
    RenewalRate,
    duration_months_for,
    n_installments,
)


class TestLoanDurationTiers:
    """Article 7 — Tableau des paliers (durée par montant)."""

    @pytest.mark.parametrize(
        "montant, expected_months",
        [
            (Decimal("5000"),    2),
            (Decimal("50000"),   2),
            (Decimal("51000"),   3),
            (Decimal("200000"),  3),
            (Decimal("201000"),  4),
            (Decimal("350000"),  4),
            (Decimal("351000"),  5),
            (Decimal("500000"),  5),
            (Decimal("501000"),  6),
            (Decimal("650000"),  6),
            (Decimal("651000"),  7),
            (Decimal("800000"),  7),
            (Decimal("801000"),  8),
            (Decimal("950000"),  8),
            (Decimal("951000"),  9),
            (Decimal("1500000"), 9),
            (Decimal("10000000"), 9),  # Article 7 : ≥ 951 000 → 9 mois fixe.
        ],
    )
    def test_all_tier_boundaries(self, montant, expected_months):
        assert duration_months_for(montant) == expected_months

    def test_rejects_amount_below_minimum(self):
        with pytest.raises(ValueError, match="minimum"):
            duration_months_for(Decimal("4999"))


class TestPaymentModality:
    """Article 8 — cadence des échéances."""

    @pytest.mark.parametrize(
        "duree, modalite, expected",
        [
            (2, PaymentModality.MENSUEL,      2),
            (5, PaymentModality.MENSUEL,      5),
            (3, PaymentModality.HEBDOMADAIRE, 12),
            (2, PaymentModality.JOURNALIER,   60),
        ],
    )
    def test_n_installments(self, duree, modalite, expected):
        assert n_installments(duree, modalite) == expected

    def test_unknown_modality_raises(self):
        with pytest.raises(ValueError, match="inconnue"):
            n_installments(3, "annuel")


class TestRegulationConstants:
    """Articles 5, 10, 11 — taux fixes."""

    def test_loan_interest_rate_is_10pct(self):
        assert LOAN_INTEREST_RATE == Decimal("0.10")

    def test_renewal_extra_months_is_one(self):
        assert RENEWAL_EXTRA_MONTHS == 1

    def test_renewal_rates(self):
        assert RenewalRate.INTERETS_AU_COMPTANT == Decimal("0.10")
        assert RenewalRate.INTERETS_REPORTES == Decimal("0.15")
        assert RenewalRate.PENALITE_NON_VERSEMENT == Decimal("0.50")
