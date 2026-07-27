"""P6 + P7 — frais d'étude d'une demande RATTACHÉE à une micro-campagne.

P6 : le montant des frais exposé (dashboard paiement manuel + clients) doit être
     celui de la CAMPAGNE (study_fee_for), pas le 5000 générique.
P7 : une campagne SANS frais (frais_etude_montant = 0) doit sauter la phase
     « frais à percevoir » après validation (status_after_prevoie → en_instruction).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import LoanRequest, MicrocreditCampaign
from apps_coop.loans.serializers import LoanRequestReadSerializer
from apps_coop.loans.services import status_after_prevoie
from apps_coop.payments.models import FeeType
from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db


def _campaign(frais):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom="Camp",
        profil_cible="commercants",
        date_debut=today - timedelta(days=1),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        actif=True,
        frais_etude_montant=frais,
        created_by=UserFactory(),
    )


def _lr(member, campaign=None):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("30000"),
        duree_mois=3,
        motif="camp",
        statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
        microcampaign=campaign,
    )


def _seed_generic_fee(montant="5000"):
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"montant": Decimal(montant), "actif": True, "libelle": "Étude"},
    )


def test_serializer_shows_campaign_fee_not_generic():
    _seed_generic_fee("5000")
    m = MemberFactory()
    lr = _lr(m, _campaign(Decimal("2000")))
    data = LoanRequestReadSerializer(lr).data
    assert Decimal(data["frais_etude_montant"]) == Decimal("2000")


def test_serializer_free_campaign_shows_zero():
    _seed_generic_fee("5000")
    m = MemberFactory()
    lr = _lr(m, _campaign(Decimal("0")))
    data = LoanRequestReadSerializer(lr).data
    assert Decimal(data["frais_etude_montant"]) == Decimal("0")


def test_status_skips_fee_phase_for_free_campaign():
    _seed_generic_fee("5000")
    m = MemberFactory()
    lr = _lr(m, _campaign(Decimal("0")))
    assert status_after_prevoie(lr) == LoanRequest.Statut.EN_INSTRUCTION


def test_status_requires_fee_phase_for_paid_campaign():
    _seed_generic_fee("5000")
    m = MemberFactory()
    lr = _lr(m, _campaign(Decimal("2000")))
    assert status_after_prevoie(lr) == LoanRequest.Statut.EN_ATTENTE


def test_non_campaign_falls_back_to_generic_fee():
    _seed_generic_fee("5000")
    m = MemberFactory()
    lr = _lr(m, None)
    data = LoanRequestReadSerializer(lr).data
    assert data["frais_etude_montant"] == "5000.00"
