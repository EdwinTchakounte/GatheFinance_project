"""Régression — frais d'étude = 0 sur une voie DIRECTE (senior_brc / garantie).

Bug trouvé en simulation locale 2026-08-10 : le seed pose ``DEMANDE_CREDIT = 0``
par défaut (frais discrétionnaire « admin to fix »). Or ``loan_request_create``
plaçait toute demande voie directe en EN_ATTENTE sans tenir compte de frais=0 :
la demande restait coincée (aucun frais à payer pour la débloquer, le comité ne
peut pas l'approuver depuis EN_ATTENTE). La voie campagne, elle, gérait déjà 0.

Correctif : voie directe + frais 0 → EN_INSTRUCTION direct (parité campagne /
status_after_prevoie). Avaliste garde sa pré-étape (EN_ATTENTE_AVALISTE).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def _fee_zero():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit", "montant": Decimal("0"), "actif": True},
    )


def _borrower(classique="250000"):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400))
    ClassicSavingsAccount.objects.create(
        member=m, solde=Decimal(classique), date_ouverture=date.today()
    )
    return m


def _client(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def test_direct_voie_zero_fee_goes_straight_to_instruction(_fee_zero):
    """senior_brc + frais 0 → EN_INSTRUCTION (plus de blocage EN_ATTENTE)."""
    m = _borrower()
    r = _client(m).post(
        "/api/v1/loans/requests/",
        {"montant_demande": "100000", "duree_mois": 3, "motif": "Marchandises"},
        format="json",
    )
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert lr.frais_demande_credit_paye is True
    assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
    assert r.json()["frais_a_payer"] is None


def test_direct_voie_positive_fee_still_waits(_fee_zero):
    """Frais > 0 → la porte des frais reste : EN_ATTENTE + frais_a_payer non nul."""
    FeeType.objects.filter(code=FeeType.Code.DEMANDE_CREDIT).update(montant=Decimal("2000"))
    m = _borrower()
    r = _client(m).post(
        "/api/v1/loans/requests/",
        {"montant_demande": "100000", "duree_mois": 3, "motif": "Marchandises"},
        format="json",
    )
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert lr.statut == LoanRequest.Statut.EN_ATTENTE
    assert lr.frais_demande_credit_paye is False
    assert r.json()["frais_a_payer"] is not None
