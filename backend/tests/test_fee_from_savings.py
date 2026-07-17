"""Paiement des frais membre (adhésion/inscription) depuis l'épargne.

G7 (carrousel home) / G5 (réactivation) — transfert interne : le Payment naît
VALIDE et déclenche le hook d'activation. Puise classique retirable + collecte.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.members.fee_from_savings_services import (
    FeePaymentError,
    pay_membership_fee_from_savings,
)
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _fee(code, montant):
    FeeType.objects.update_or_create(
        code=code, defaults={"montant": Decimal(montant), "actif": True, "libelle": code}
    )


def _classic(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


class TestService:
    def test_regle_adhesion_depuis_epargne(self):
        _fee("ADHESION", "10000")
        m = MemberFactory()
        acc = _classic(m, "25000")

        payment = pay_membership_fee_from_savings(m, "ADHESION")

        assert payment.type == Payment.Type.FRAIS_ADHESION
        assert payment.source == Payment.Source.DEDUCTION_EPARGNE
        assert payment.statut == Payment.Statut.VALIDE
        acc.refresh_from_db()
        assert acc.solde == Decimal("15000.00")

    def test_refuse_si_insuffisant(self):
        _fee("ADHESION", "10000")
        m = MemberFactory()
        _classic(m, "3000")
        with pytest.raises(FeePaymentError):
            pay_membership_fee_from_savings(m, "ADHESION")

    def test_code_non_supporte(self):
        m = MemberFactory()
        _classic(m, "50000")
        with pytest.raises(FeePaymentError):
            pay_membership_fee_from_savings(m, "CARNET")


class TestEndpoints:
    def test_status_endpoint(self):
        _fee("ADHESION", "10000")
        _fee("INSCRIPTION", "2000")
        m = MemberFactory()
        _classic(m, "15000")
        r = _api(m.user).get("/api/v1/me/fees/")
        assert r.status_code == 200
        assert r.data["fees"]["ADHESION"]["montant"] == "10000.00"
        assert r.data["fees"]["ADHESION"]["solvable"] is True
        assert r.data["fees"]["INSCRIPTION"]["solvable"] is True

    def test_status_insolvable(self):
        _fee("ADHESION", "10000")
        m = MemberFactory()
        _classic(m, "1000")
        r = _api(m.user).get("/api/v1/me/fees/")
        assert r.data["fees"]["ADHESION"]["solvable"] is False

    def test_pay_endpoint(self):
        _fee("INSCRIPTION", "2000")
        m = MemberFactory()
        acc = _classic(m, "5000")
        r = _api(m.user).post("/api/v1/me/fees/INSCRIPTION/pay-from-savings/")
        assert r.status_code == 200
        acc.refresh_from_db()
        assert acc.solde == Decimal("3000.00")


class TestGraceDays:
    def test_defaut_grace_10_jours(self):
        from apps_coop.members.tasks import DEFAULT_GRACE_DAYS

        assert DEFAULT_GRACE_DAYS == 10
