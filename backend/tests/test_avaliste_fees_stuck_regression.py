"""Régression 2026-07-20 — voie AVALISTE bloquée en « frais à percevoir ».

Bug rapporté : une demande de crédit par la voie avaliste, une fois l'avaliste
ayant accepté ET les frais d'étude encaissés, restait affichée dans « frais à
percevoir » côté admin. Un second encaissement était refusé (« frais déjà
réglés ») : la demande était donc coincée en ``EN_ATTENTE`` avec
``frais_demande_credit_paye=True``.

Deux causes :
  1. ``open_instruction_after_fees`` re-sollicitait l'avaliste alors qu'un
     ``AvalisteConsent`` existait déjà (accepté) → ``ValueError`` avalée → statut
     laissé en EN_ATTENTE.
  2. ``status_after_prevoie`` renvoyait EN_ATTENTE dès qu'un tarif d'étude était
     configuré, sans regarder si les frais étaient DÉJÀ payés.

On couvre les deux ordres d'exécution (« avaliste d'abord » et « frais d'abord »)
+ la visibilité des rejets avaliste dans l'onglet « Rejetées ».
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import (
    request_avaliste_consent,
    respond_to_avaliste_consent,
)
from apps_coop.loans.models import AvalisteConsent, LoanRequest
from apps_coop.loans.services import status_after_prevoie
from apps_coop.loans.study_fee_services import open_instruction_after_fees
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


@pytest.fixture
def fee_5000():
    fee, _ = FeeType.objects.get_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit"},
    )
    fee.montant = Decimal("5000")
    fee.actif = True
    fee.save()
    return fee


def _member(*, classique=Decimal("0")):
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400))
    if classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m, solde=classique, date_ouverture=date.today()
        )
    return m


def _avaliste_request(borrower, avaliste, *, montant=Decimal("50000")):
    """LR en attente de frais, avaliste DÉSIGNÉ (comme à la soumission)."""
    return LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=3,
        motif="Crédit voie avaliste",
        statut=LoanRequest.Statut.EN_ATTENTE,
        frais_demande_credit_paye=False,
        avaliste_numero_saisi=avaliste.numero_membre,
        avaliste_nom_saisi=avaliste.nom,
    )


class TestAvalisteFirstThenFees:
    """Ordre « avaliste accepte, PUIS le membre paie les frais »."""

    def test_accept_keeps_fees_gate_then_fees_open_instruction(self, fee_5000):
        borrower = _member(classique=Decimal("10000"))
        avaliste = _member(classique=Decimal("100000"))
        lr = _avaliste_request(borrower, avaliste)

        # 1. Sollicitation (bouton admin) → EN_ATTENTE_AVALISTE.
        consent = request_avaliste_consent(
            lr, numero_identification=avaliste.numero_membre, nom=avaliste.nom
        )
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE

        # 2. L'avaliste accepte. Frais encore dus → porte des frais.
        respond_to_avaliste_consent(consent, accept=True)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE  # « frais à payer »
        assert lr.frais_demande_credit_paye is False

        # 3. Les frais sont encaissés → l'instruction s'ouvre. On ne
        #    re-sollicite PAS l'avaliste, et aucun second consent n'est créé.
        open_instruction_after_fees(lr)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
        assert lr.frais_demande_credit_paye is True
        assert AvalisteConsent.objects.filter(loan_request=lr).count() == 1


class TestFeesFirstThenAvaliste:
    """Ordre « frais d'abord, avaliste ensuite » (parcours historique)."""

    def test_fees_solicit_then_accept_reaches_instruction(self, fee_5000):
        borrower = _member(classique=Decimal("10000"))
        avaliste = _member(classique=Decimal("100000"))
        lr = _avaliste_request(borrower, avaliste)

        # 1. Frais payés → sollicitation de l'avaliste → EN_ATTENTE_AVALISTE.
        open_instruction_after_fees(lr)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        assert lr.frais_demande_credit_paye is True

        # 2. L'avaliste accepte. Frais DÉJÀ payés → instruction directe,
        #    surtout pas un retour en EN_ATTENTE (« frais à percevoir »).
        consent = lr.avaliste_consent
        respond_to_avaliste_consent(consent, accept=True)
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION


class TestStatusAfterPrevoieFeeAware:
    def test_paid_fees_go_straight_to_instruction(self, fee_5000):
        lr = LoanRequest(
            montant_demande=Decimal("50000"),
            duree_mois=3,
            frais_demande_credit_paye=True,
        )
        assert status_after_prevoie(lr) == LoanRequest.Statut.EN_INSTRUCTION

    def test_unpaid_fees_hit_the_gate(self, fee_5000):
        lr = LoanRequest(
            montant_demande=Decimal("50000"),
            duree_mois=3,
            frais_demande_credit_paye=False,
        )
        assert status_after_prevoie(lr) == LoanRequest.Statut.EN_ATTENTE


class TestRejectedListIncludesAvaliste:
    """L'onglet « Rejetées » doit inclure les rejets avaliste et campagne."""

    def test_rejetee_filter_returns_avaliste_refusal(self, admin_user):
        borrower = _member(classique=Decimal("10000"))
        lr = LoanRequest.objects.create(
            member=borrower,
            montant_demande=Decimal("50000"),
            duree_mois=3,
            motif="Refusée par l'avaliste",
            statut=LoanRequest.Statut.REJETEE_AVALISTE,
            motif_rejet="Refus de l'avaliste.",
        )
        client = APIClient()
        client.force_authenticate(admin_user)
        resp = client.get("/api/v1/loans/admin/requests/?statut=rejetee")
        assert resp.status_code == 200, resp.content
        ids = {row["id"] for row in resp.json()}
        assert lr.id in ids
