"""Réponse du membre à une contre-proposition du comité.

Le statut ``en_attente_acceptation_membre`` (le comité propose un montant/durée
révisés) n'avait AUCUNE transition de sortie → la demande restait figée et
bloquait toute nouvelle demande. Ces tests couvrent les deux issues :

  - ACCEPTER : la demande adopte le montant révisé et repasse en
    ``en_instruction`` (le comité finalise via son flow normal).
  - REFUSER : la demande passe en ``rejetee`` ; le membre est libéré.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


@pytest.fixture
def contre_proposition(active_member):
    """Demande avec une contre-proposition du comité en attente de réponse."""
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test contre-proposition.",
        statut=LoanRequest.Statut.EN_ATTENTE_ACCEPTATION_MEMBRE,
        montant_revise=Decimal("70000"),
        duree_revisee=4,
    )


def _client(member):
    c = APIClient()
    c.force_authenticate(member.user)
    return c


class TestAccept:
    def test_accept_applies_revised_and_returns_to_instruction(
        self, contre_proposition, active_member
    ):
        c = _client(active_member)
        r = c.post(
            f"/api/v1/loans/me/requests/{contre_proposition.id}/counter-proposal/accept/"
        )
        assert r.status_code == 200, r.content

        contre_proposition.refresh_from_db()
        assert contre_proposition.statut == LoanRequest.Statut.EN_INSTRUCTION
        assert Decimal(contre_proposition.montant_demande) == Decimal("70000")
        assert contre_proposition.duree_mois == 4

    def test_accept_wrong_status_409(self, active_member):
        lr = LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("50000"),
            duree_mois=3,
            motif="x",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
        )
        r = _client(active_member).post(
            f"/api/v1/loans/me/requests/{lr.id}/counter-proposal/accept/"
        )
        assert r.status_code == 409, r.content
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

    def test_other_member_cannot_accept_404(self, contre_proposition):
        intruder = MemberFactory()
        r = _client(intruder).post(
            f"/api/v1/loans/me/requests/{contre_proposition.id}/counter-proposal/accept/"
        )
        assert r.status_code == 404, r.content


class TestRefuse:
    def test_refuse_marks_rejected_with_motif(
        self, contre_proposition, active_member
    ):
        c = _client(active_member)
        r = c.post(
            f"/api/v1/loans/me/requests/{contre_proposition.id}/counter-proposal/refuse/",
            {"motif": "Montant trop faible."},
            format="json",
        )
        assert r.status_code == 200, r.content

        contre_proposition.refresh_from_db()
        assert contre_proposition.statut == LoanRequest.Statut.REJETEE
        assert contre_proposition.motif_rejet == "Montant trop faible."
        # Le montant d'origine n'est pas modifié par un refus.
        assert Decimal(contre_proposition.montant_demande) == Decimal("100000")

    def test_refuse_without_motif_uses_default(
        self, contre_proposition, active_member
    ):
        r = _client(active_member).post(
            f"/api/v1/loans/me/requests/{contre_proposition.id}/counter-proposal/refuse/"
        )
        assert r.status_code == 200, r.content
        contre_proposition.refresh_from_db()
        assert contre_proposition.statut == LoanRequest.Statut.REJETEE
        assert contre_proposition.motif_rejet  # non vide

    def test_refuse_wrong_status_409(self, active_member):
        lr = LoanRequest.objects.create(
            member=active_member,
            montant_demande=Decimal("50000"),
            duree_mois=3,
            motif="x",
            statut=LoanRequest.Statut.EN_ATTENTE,
        )
        r = _client(active_member).post(
            f"/api/v1/loans/me/requests/{lr.id}/counter-proposal/refuse/"
        )
        assert r.status_code == 409, r.content
