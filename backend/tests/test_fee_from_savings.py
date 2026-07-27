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
from tests.factories import MemberFactory, SuspendedMemberFactory

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
        # Un membre règle ses frais quand il est NON actif (activation en cours) :
        # un compte déjà actif est bloqué (cf. garde P1 « déjà réglés »).
        m = SuspendedMemberFactory()
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
        # Un code hors des 3 frais d'activation reste refusé.
        m = MemberFactory()
        _classic(m, "50000")
        with pytest.raises(FeePaymentError):
            pay_membership_fee_from_savings(m, "DEMANDE_CREDIT")

    def test_trois_frais_depuis_epargne_active_le_membre(self):
        # Cœur du fix : un membre suspendu qui règle les 3 frais depuis son
        # épargne (dont le carnet) passe ACTIF. Avant, le carnet n'était pas
        # réglable depuis l'épargne → activation impossible par cette voie.
        from apps_coop.members.models import Member

        _fee("ADHESION", "10000")
        _fee("INSCRIPTION", "2000")
        _fee("CARNET", "1000")
        m = SuspendedMemberFactory()
        _classic(m, "13000")

        pay_membership_fee_from_savings(m, "ADHESION")
        pay_membership_fee_from_savings(m, "INSCRIPTION")
        m.refresh_from_db()
        assert m.statut == Member.Statut.SUSPENDU  # 2/3 → toujours suspendu
        pay_membership_fee_from_savings(m, "CARNET")
        m.refresh_from_db()
        assert m.statut == Member.Statut.ACTIF  # 3/3 → activé

    def test_regle_carnet_depuis_epargne(self):
        # Le carnet (3e frais d'activation) est désormais réglable depuis
        # l'épargne : Payment VALIDE + BookletOrder créé via _hook_carnet_fees.
        from apps_coop.members.models import BookletOrder

        _fee("CARNET", "1000")
        m = SuspendedMemberFactory()
        acc = _classic(m, "5000")

        payment = pay_membership_fee_from_savings(m, "CARNET")

        assert payment.type == Payment.Type.FRAIS_CARNET
        assert payment.source == Payment.Source.DEDUCTION_EPARGNE
        assert payment.statut == Payment.Statut.VALIDE
        acc.refresh_from_db()
        assert acc.solde == Decimal("4000.00")
        assert BookletOrder.objects.filter(member=m, payment=payment).exists()


class TestEndpoints:
    def test_status_endpoint(self):
        _fee("ADHESION", "10000")
        _fee("INSCRIPTION", "2000")
        _fee("CARNET", "1000")
        m = SuspendedMemberFactory()
        _classic(m, "15000")
        r = _api(m.user).get("/api/v1/me/fees/")
        assert r.status_code == 200
        # Les TROIS frais d'activation sont exposés (carnet inclus).
        assert set(r.data["fees"].keys()) == {"ADHESION", "INSCRIPTION", "CARNET"}
        assert r.data["fees"]["ADHESION"]["montant"] == "10000.00"
        assert r.data["fees"]["CARNET"]["montant"] == "1000.00"
        assert r.data["fees"]["CARNET"]["solvable"] is True
        # Rien n'est encore réglé.
        assert all(not f["paye"] for f in r.data["fees"].values())

    def test_status_reflects_paid_fee(self):
        _fee("CARNET", "1000")
        m = SuspendedMemberFactory()
        _classic(m, "5000")
        pay_membership_fee_from_savings(m, "CARNET")
        r = _api(m.user).get("/api/v1/me/fees/")
        assert r.data["fees"]["CARNET"]["paye"] is True

    def test_status_insolvable(self):
        _fee("ADHESION", "10000")
        m = MemberFactory()
        _classic(m, "1000")
        r = _api(m.user).get("/api/v1/me/fees/")
        assert r.data["fees"]["ADHESION"]["solvable"] is False

    def test_pay_endpoint(self):
        _fee("INSCRIPTION", "2000")
        m = SuspendedMemberFactory()
        acc = _classic(m, "5000")
        r = _api(m.user).post("/api/v1/me/fees/INSCRIPTION/pay-from-savings/")
        assert r.status_code == 200
        acc.refresh_from_db()
        assert acc.solde == Decimal("3000.00")


class TestGraceDays:
    def test_defaut_grace_10_jours(self):
        from apps_coop.members.tasks import DEFAULT_GRACE_DAYS

        assert DEFAULT_GRACE_DAYS == 10
