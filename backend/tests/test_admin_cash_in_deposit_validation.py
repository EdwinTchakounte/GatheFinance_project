"""Versement manuel agence (`POST /payments/admin/cash-in/`) — le cash-in admin
applique désormais les MÊMES règles de versement que le canal membre.

Avant le fix 2026-07-21, ce endpoint créait des dépôts SANS validation :
  * R1 — collecte : ni pas de 50 FCFA, ni minimum/jour ;
  * R2 — classique : ni gate `config.actif`, ni plancher 1 000, ni plafond ;
  * R3 — classique : `is_placement=True` accepté hors fenêtre → écriture marquée
    « placement » sans tranche prêteur (argent NON gelé mais annoncé comme placé).

Ces tests figent l'alignement sur `apps_coop/payments/deposit_validation.py`.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.savings.models import (
    ClassicSavingsConfig,
    ClassicSavingsTransaction,
    SavingsTransaction,
)


pytestmark = pytest.mark.django_db

CASH_IN = "/api/v1/payments/admin/cash-in/"


def _admin_client(admin_user) -> APIClient:
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


def _post(client, member, **body):
    return client.post(CASH_IN, {"member_id": member.id, **body}, format="json")


# ---------------------------------------------------------------------------
# R1 — collecte : pas de 50 FCFA + minimum/jour
# ---------------------------------------------------------------------------
class TestR1CollecteAmountRules:
    def test_non_multiple_of_step_rejected(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="1037")
        assert r.status_code == 400, r.content
        assert b"multiple" in r.content
        assert not SavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_below_min_per_day_rejected(self, active_member, admin_user):
        # 950 est multiple de 50 mais < 1 000/jour → refus.
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="950")
        assert r.status_code == 400, r.content
        assert not SavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_valid_collecte_accepted(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="1000")
        assert r.status_code == 201, r.content
        assert SavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=SavingsTransaction.TypeOp.DEPOT,
        ).count() == 1


# ---------------------------------------------------------------------------
# R2 — classique : gate config.actif + plancher 1 000 + plafond
# ---------------------------------------------------------------------------
class TestR2ClassiqueAmountRules:
    def test_below_floor_rejected(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="500")
        assert r.status_code == 400, r.content
        assert b"minimum" in r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_closed_product_rejected(self, active_member, admin_user):
        cfg = ClassicSavingsConfig.get_solo()
        cfg.actif = False
        cfg.save(update_fields=["actif"])
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="5000")
        assert r.status_code == 400, r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_above_max_rejected(self, active_member, admin_user):
        cfg = ClassicSavingsConfig.get_solo()
        cfg.actif = True
        cfg.depot_max = 100000
        cfg.save(update_fields=["actif", "depot_max"])
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="200000")
        assert r.status_code == 400, r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_valid_classique_accepted(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="5000")
        assert r.status_code == 201, r.content
        assert ClassicSavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        ).count() == 1


# ---------------------------------------------------------------------------
# R3 — placement hors fenêtre refusé (pas d'écriture « placement » sans tranche)
# ---------------------------------------------------------------------------
class TestRemboursementGuards:
    """BUG-1/BUG-2 — le cash-in remboursement admin doit refuser un crédit non
    remboursable et un trop-perçu, comme le canal membre (sinon argent perdu)."""

    def test_over_payment_rejected(self, active_member, admin_user):
        from apps_coop.loans.models import Loan
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        assert loan.statut == Loan.Statut.ACTIF
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant=str(int(loan.solde_restant) + 5000),
        )
        assert r.status_code == 400, r.content
        assert b"solde restant" in r.content

    def test_closed_loan_rejected(self, active_member, admin_user):
        from apps_coop.loans.models import Loan
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant="1000",
        )
        assert r.status_code == 400, r.content

    def test_valid_repayment_accepted(self, active_member, admin_user):
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant="1000",
        )
        assert r.status_code == 201, r.content


class TestR3PlacementWindow:
    def test_placement_when_closed_rejected(self, active_member, admin_user):
        # Ferme le placement globalement.
        AppSetting.objects.update_or_create(
            cle="epargne.placement.enabled",
            defaults={"valeur": "false", "description": ""},
        )
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )
        assert r.status_code == 400, r.content
        assert b"LIBRE" in r.content
        # Aucune écriture créée (ni placement, ni libre) — le refus est total.
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_libre_still_accepted_when_placement_closed(self, active_member, admin_user):
        AppSetting.objects.update_or_create(
            cle="epargne.placement.enabled",
            defaults={"valeur": "false", "description": ""},
        )
        # Même produit fermé au placement, un dépôt LIBRE passe.
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=False,
        )
        assert r.status_code == 201, r.content
        tx = ClassicSavingsTransaction.objects.get(account__member=active_member)
        assert tx.is_placement is False
