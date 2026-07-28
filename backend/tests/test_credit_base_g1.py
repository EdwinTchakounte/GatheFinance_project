"""G1 — base obligatoire : apport personnel GELÉ = 20 % du montant (éditable).

Socle gouvernance : le membre détient 30 % (20 % apport gelé + 10 % intérêt coupé
à la source — ce dernier déjà géré par le mode source existant). Ici on verrouille
le volet APPORT : le gel demandeur sur la voie senior_brc sous-couverte = 20 %
(loans.apport.rate), borné à l'épargne disponible.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _seed_fee():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Étude", "montant": Decimal("1000"), "actif": True},
    )


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _member_with_savings(amount):
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30 * 18)  # ancien (voie ouverte)
    m.save(update_fields=["date_adhesion"])
    ClassicSavingsAccount.objects.update_or_create(
        member=m, defaults={"solde": Decimal(amount), "date_ouverture": date.today()}
    )
    return m


def _post_credit(member, montant="100000"):
    return _api(member).post(
        "/api/v1/loans/requests/",
        {"montant_demande": montant, "duree_mois": 6, "motif": "Fonds de roulement boutique"},
        format="json",
    )


def test_gel_apport_20pct():
    """Épargne 30 % (sous-couvert) → gel = 20 % du montant (base G1)."""
    _seed_fee()
    m = _member_with_savings("30000")  # 30 % de 100 000
    r = _post_credit(m)
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert lr.montant_gele_demandeur == Decimal("20000")  # 20 % × 100 000


def test_taux_apport_editable():
    """Le taux d'apport gelé est piloté par loans.apport.rate (règlement)."""
    _seed_fee()
    AppSetting.objects.update_or_create(
        cle="loans.apport.rate", defaults={"valeur": "0.25"}
    )
    m = _member_with_savings("40000")
    r = _post_credit(m)
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert lr.montant_gele_demandeur == Decimal("25000")  # 25 % × 100 000
