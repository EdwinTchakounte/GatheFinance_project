"""Carnet obligatoire pour les bénéficiaires créés via campagne (2026).

Un membre créé via campagne doit posséder un carnet — les écritures collecte
s'imputent au carnet. Le carnet est facturé et réglé à la demande de crédit :
tant qu'il n'est pas payé/créé, la demande reste EN_ATTENTE (même quand les
frais d'étude sont nuls). À son règlement, l'instruction s'ouvre.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.microcampaign_services import accept_campaign_application
from apps_coop.loans.models import (
    CampaignApplication,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.loans.services import campaign_member_needs_carnet
from apps_coop.members.models import BookletOrder
from apps_coop.payments.models import FeeType, Payment
from apps_coop.payments.services import _hook_carnet_fees

from tests.factories import UserFactory


pytestmark = pytest.mark.django_db(transaction=True)


def _campaign(*, frais_etude=Decimal("0")):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom="Campagne carnet test",
        profil_cible="commercants",
        date_debut=today - timedelta(days=1),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"),
        montant_max=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        membre_requis=False,
        frais_etude_montant=frais_etude,
        actif=True,
        created_by=UserFactory(),
    )


def _application(campaign):
    return CampaignApplication.objects.create(
        campaign=campaign,
        nom="NGONO",
        prenom="Alice",
        phone="+237690000000",
        email="alice.ngono@test.local",
        montant_demande=Decimal("50000"),
        motif="Fonds de commerce",
        statut=CampaignApplication.Statut.EN_ATTENTE,
    )


def _seed_carnet_fee(montant="2000"):
    FeeType.objects.update_or_create(
        code=FeeType.Code.CARNET,
        defaults={"libelle": "Frais de carnet", "montant": Decimal(montant), "actif": True},
    )


def _pay_carnet(member, montant="2000"):
    """Simule le règlement du carnet (paiement validé → hook)."""
    import uuid

    from django.utils import timezone

    payment = Payment.objects.create(
        member=member,
        montant=Decimal(montant),
        type=Payment.Type.FRAIS_CARNET,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
        idempotency_key=uuid.uuid4(),
    )
    _hook_carnet_fees(payment, {})
    return payment


def test_accepted_beneficiary_waits_for_carnet_even_if_study_free(admin_user):
    _seed_carnet_fee()
    campaign = _campaign(frais_etude=Decimal("0"))
    app = _application(campaign)

    accept_campaign_application(app, decided_by=admin_user)
    app.refresh_from_db()
    member = app.member
    assert member is not None
    # Étude gratuite MAIS carnet obligatoire pas encore réglé → EN_ATTENTE.
    assert campaign_member_needs_carnet(member) is True
    assert not BookletOrder.objects.filter(member=member).exists()
    lr = LoanRequest.objects.get(member=member)
    assert lr.statut == LoanRequest.Statut.EN_ATTENTE
    assert lr.frais_demande_credit_paye is True  # rien à payer côté étude


def test_paying_carnet_creates_booklet_and_opens_instruction(admin_user):
    _seed_carnet_fee()
    campaign = _campaign(frais_etude=Decimal("0"))
    app = _application(campaign)
    accept_campaign_application(app, decided_by=admin_user)
    app.refresh_from_db()
    member = app.member

    _pay_carnet(member)

    # Carnet créé → écritures pourront s'y imputer, et l'instruction s'ouvre.
    assert BookletOrder.objects.filter(member=member).exists()
    assert campaign_member_needs_carnet(member) is False
    lr = LoanRequest.objects.get(member=member)
    assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION


def test_study_fee_paid_alone_does_not_open_instruction(admin_user):
    # Frais d'étude payés mais carnet toujours dû → reste EN_ATTENTE.
    _seed_carnet_fee()
    campaign = _campaign(frais_etude=Decimal("3000"))
    app = _application(campaign)
    accept_campaign_application(app, decided_by=admin_user)
    app.refresh_from_db()
    member = app.member
    lr = LoanRequest.objects.get(member=member)
    assert lr.statut == LoanRequest.Statut.EN_ATTENTE

    # Règlement des frais d'étude uniquement.
    from apps_coop.loans.study_fee_services import open_instruction_after_fees

    open_instruction_after_fees(lr)
    lr.refresh_from_db()
    # Carnet toujours dû → l'instruction NE s'ouvre PAS.
    assert lr.statut == LoanRequest.Statut.EN_ATTENTE
    assert lr.frais_demande_credit_paye is True

    # Puis carnet réglé → instruction ouverte.
    _pay_carnet(member, montant="2000")
    lr.refresh_from_db()
    assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION


def test_non_campaign_member_never_needs_carnet(active_member):
    # Un membre ordinaire (pas d'origine campagne) n'est pas concerné.
    assert campaign_member_needs_carnet(active_member) is False
