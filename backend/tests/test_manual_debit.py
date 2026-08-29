"""Débit manuel agence (retrait direct + prélèvement de frais depuis l'épargne)."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.payments.manual_debit_services import ManualDebitError, manual_debit
from apps_coop.payments.models import FeeType, Payment
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)


class TestSimpleDebit:
    def test_debit_classique(self):
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=_JAN
        )
        res = manual_debit(
            member=m, compte="classique", montant=Decimal("20000"),
            motif="Retrait agence",
        )
        assert Decimal(res["solde_apres"]) == Decimal("30000")
        assert ClassicSavingsAccount.objects.get(member=m).solde == Decimal("30000")

    def test_debit_collecte(self):
        m = MemberFactory()
        SavingsAccount.objects.update_or_create(
            member=m,
            defaults={"solde": Decimal("8000"), "date_ouverture": _JAN},
        )
        res = manual_debit(member=m, compte="collecte", montant=Decimal("3000"))
        assert Decimal(res["solde_apres"]) == Decimal("5000")

    def test_debit_refuse_si_insuffisant(self):
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("1000"), date_ouverture=_JAN
        )
        with pytest.raises(ManualDebitError, match="insuffisant"):
            manual_debit(member=m, compte="classique", montant=Decimal("5000"))


class TestFeeDebit:
    def test_pay_carnet_fee_from_savings(self, admin_user):
        FeeType.objects.update_or_create(
            code=FeeType.Code.CARNET,
            defaults={"libelle": "Carnet", "montant": 1000, "actif": True},
        )
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("50000"), date_ouverture=_JAN
        )
        res = manual_debit(
            member=m, fee_code=FeeType.Code.CARNET, is_renewal=True,
            actor=admin_user,
        )
        # Débité du barème officiel + Payment de frais créé + hook exécuté (carnet).
        assert Decimal(res["montant"]) == Decimal("1000")
        assert ClassicSavingsAccount.objects.get(member=m).solde == Decimal("49000")
        p = Payment.objects.get(pk=res["payment_id"])
        assert p.type == Payment.Type.FRAIS_CARNET
        assert p.source == Payment.Source.DEDUCTION_EPARGNE
        from apps_coop.members.models import BookletOrder
        assert BookletOrder.objects.filter(member=m).exists()  # hook a tourné


class TestApi:
    def test_manual_debit_via_api(self, admin_user):
        m = MemberFactory()
        ClassicSavingsAccount.objects.create(
            member=m, solde=Decimal("40000"), date_ouverture=_JAN
        )
        c = APIClient()
        c.force_authenticate(user=admin_user)
        r = c.post(
            "/api/v1/payments/admin/manual-debit/",
            {"member_id": m.id, "compte": "classique", "montant": 15000,
             "motif": "Frais fin d'année"},
            format="json",
        )
        assert r.status_code == 200, r.content
        assert Decimal(r.json()["solde_apres"]) == Decimal("25000")

    def test_requires_admin(self, staff_user):
        m = MemberFactory()
        c = APIClient()
        c.force_authenticate(user=staff_user)  # staff mais pas admin
        r = c.post(
            "/api/v1/payments/admin/manual-debit/",
            {"member_id": m.id, "compte": "classique", "montant": 1000},
            format="json",
        )
        assert r.status_code == 403
