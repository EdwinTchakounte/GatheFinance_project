"""Frais d'étude sur TOUTES les voies + action admin (encaissement hors app).

Réforme flux 2026 : le statut `en_attente` = « frais à payer » devient la porte
commune à toutes les voies (auto-couverture / avaliste / campagne). L'admin peut
aussi enregistrer un règlement encaissé hors app (espèces agence).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.loans.services import status_after_prevoie, study_fee_for
from apps_coop.payments.models import FeeType, Payment

pytestmark = pytest.mark.django_db


def _set_study_fee(montant: str):
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit", "montant": Decimal(montant), "actif": True},
    )


def _lr(member, statut=LoanRequest.Statut.EN_ATTENTE):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("60000"),
        duree_mois=3,
        motif="Test",
        statut=statut,
    )


class TestRoutageFrais:
    def test_frais_dus_route_vers_en_attente(self, active_member):
        _set_study_fee("3000")
        lr = _lr(active_member)
        assert status_after_prevoie(lr) == LoanRequest.Statut.EN_ATTENTE

    def test_etude_gratuite_route_direct_instruction(self, active_member):
        _set_study_fee("0")
        lr = _lr(active_member)
        assert status_after_prevoie(lr) == LoanRequest.Statut.EN_INSTRUCTION

    def test_study_fee_for_defaut_feetype(self, active_member):
        _set_study_fee("5000")
        assert study_fee_for(None) == Decimal("5000")


class TestAdminRecordStudyFee:
    def test_admin_encaisse_les_frais_hors_app(self, active_member, admin_user):
        _set_study_fee("3000")
        lr = _lr(active_member, statut=LoanRequest.Statut.EN_ATTENTE)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        r = client.post(
            f"/api/v1/loans/requests/{lr.id}/study-fee/",
            {"reference": "CASH-AGENCE-1"},
            format="json",
        )
        assert r.status_code == 200, r.content
        lr.refresh_from_db()
        # La demande a franchi la porte des frais → instruction.
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
        # Un paiement manuel validé a été tracé.
        pay = Payment.objects.filter(
            member=active_member, type=Payment.Type.FRAIS_DEMANDE_CREDIT
        ).latest("id")
        assert pay.statut == Payment.Statut.VALIDE
        assert pay.montant == Decimal("3000")
        assert pay.reference_externe == "CASH-AGENCE-1"

    def test_refuse_si_pas_en_attente(self, active_member, admin_user):
        _set_study_fee("3000")
        lr = _lr(active_member, statut=LoanRequest.Statut.EN_INSTRUCTION)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        r = client.post(f"/api/v1/loans/requests/{lr.id}/study-fee/", {}, format="json")
        assert r.status_code == 400
