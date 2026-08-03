"""Attribut BRC — déclaration « a fréquenté le centre de formation BRC ».

BRC n'est PAS une voie : c'est un ATTRIBUT informatif couplable à n'importe
quelle voie (campagne, avaliste, garantie, ancienneté). Il n'entre ni dans le
routage ni dans l'éligibilité (le comité juge à l'évaluation). Ces tests
couvrent : la déclaration à la soumission, le couplage avec une voie non-senior
(garantie matérielle), le défaut False, l'exposition serializer, et le libellé
de voie décorrélé de « BRC ».
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.loans.serializers import LoanRequestReadSerializer
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _seed_fee():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais", "montant": Decimal("1000"), "actif": True},
    )


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _classic(member, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=member,
        defaults={"solde": Decimal(amount), "date_ouverture": date.today()},
    )


def test_brc_couples_with_garantie_materielle():
    """BRC déclaré SUR une demande garantie matérielle → la voie reste
    garantie_materielle ET is_brc=True (couplage attribut × voie)."""
    _seed_fee()
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30)
    m.save(update_fields=["date_adhesion"])
    r = _api(m).post(
        "/api/v1/loans/requests/",
        {
            "montant_demande": "100000",
            "duree_mois": 6,
            "motif": "Achat matériel",
            "garantie_materielle": True,
            "garantie_description": "Terrain titré",
            "is_brc": True,
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["route"] == "garantie_materielle"
    assert body["loan_request"]["is_brc"] is True
    assert body["loan_request"]["voie"] == "garantie_materielle"
    lr = LoanRequest.objects.get(pk=body["loan_request"]["id"])
    assert lr.is_brc is True


def test_brc_couples_with_senior_apport_voie():
    """BRC déclaré sur la voie par défaut (ancienneté / apport)."""
    _seed_fee()
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30)
    m.save(update_fields=["date_adhesion"])
    _classic(m, Decimal("100000"))  # couvre l'apport requis
    r = _api(m).post(
        "/api/v1/loans/requests/",
        {
            "montant_demande": "100000",
            "duree_mois": 6,
            "motif": "Fonds de roulement",
            "is_brc": True,
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["route"] == "senior_brc"
    assert body["loan_request"]["is_brc"] is True


def test_brc_defaults_false_when_not_declared():
    _seed_fee()
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30)
    m.save(update_fields=["date_adhesion"])
    _classic(m, Decimal("100000"))
    r = _api(m).post(
        "/api/v1/loans/requests/",
        {
            "montant_demande": "100000",
            "duree_mois": 6,
            "motif": "Sans BRC",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.json()["loan_request"]["is_brc"] is False


def test_brc_not_a_routing_signal():
    """is_brc ne doit RIEN changer au routage : une demande is_brc sans autre
    voie reste sur la voie par défaut senior_brc (pas de voie « brc »)."""
    _seed_fee()
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30)
    m.save(update_fields=["date_adhesion"])
    _classic(m, Decimal("100000"))
    r = _api(m).post(
        "/api/v1/loans/requests/",
        {"montant_demande": "100000", "duree_mois": 6, "motif": "x", "is_brc": True},
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.json()["loan_request"]["voie"] == "senior_brc"


def test_voie_label_decoupled_from_brc():
    """Le libellé de la voie par défaut ne contient plus « BRC » ni « Ancienneté »
    (auto-couverture épargne — décision cliente 2026-08 : « Ancienneté » n'est pas
    une voie ; libellé neutre « Sur mon épargne »)."""
    labels = LoanRequestReadSerializer._VOIE_LABELS
    assert labels["senior_brc"] == "Sur mon épargne"
    assert "BRC" not in labels["senior_brc"]
    assert "Ancienneté" not in labels["senior_brc"]
