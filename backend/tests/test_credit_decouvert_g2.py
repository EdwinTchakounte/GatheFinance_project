"""G2 — décomposition gagé / découvert figée à l'octroi.

Le crédit enregistre `montant_gage` (part adossée) et `montant_decouvert`
(part prêtée sur confiance = exposition coop). Base du suivi (G5).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps_coop.loans.models import LoanRequest, MicrocreditCampaign
from apps_coop.loans.services import approve_loan_request
from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


def _comite():
    u = User.objects.create_user(
        email=f"comite-{User.objects.count()}@g.test",
        password="x",
        username=f"comite-{User.objects.count()}",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _lr(member, *, montant="100000", gele="0", microcampaign=None, garantie=False):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal(montant),
        duree_mois=3,
        motif="Test G2 découvert",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
        montant_gele_demandeur=Decimal(gele),
        microcampaign=microcampaign,
        garantie_materielle=garantie,
    )


def _approve(lr, comite_user):
    return approve_loan_request(
        lr,
        decided_by=comite_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )


def test_apport_sous_couvert_decouvert_80():
    member = MemberFactory()
    comite = _comite()
    lr = _lr(member, montant="100000", gele="20000")  # apport 20 %
    loan = _approve(lr, comite)
    loan.refresh_from_db()
    assert loan.montant_gage == Decimal("20000.00")
    assert loan.montant_decouvert == Decimal("80000.00")


def test_auto_couvert_decouvert_zero():
    member = MemberFactory()
    comite = _comite()
    lr = _lr(member, montant="100000", gele="100000")  # épargne couvre tout
    loan = _approve(lr, comite)
    loan.refresh_from_db()
    assert loan.montant_gage == Decimal("100000.00")
    assert loan.montant_decouvert == Decimal("0.00")


def test_campagne_risque_externalise_decouvert_zero():
    member = MemberFactory()
    comite = _comite()
    camp = MicrocreditCampaign.objects.create(
        nom="Camp", profil_cible="commercants",
        date_debut=date.today() - timedelta(days=1),
        date_fin=date.today() + timedelta(days=30),
        montant_min=Decimal("5000"), montant_max=Decimal("200000"),
        taux_interet=Decimal("0.10"), nb_jours_recouvrement=60, actif=True,
        created_by=UserFactory(),
    )
    lr = _lr(member, montant="100000", gele="0", microcampaign=camp)
    loan = _approve(lr, comite)
    loan.refresh_from_db()
    assert loan.montant_gage == Decimal("100000.00")
    assert loan.montant_decouvert == Decimal("0.00")
