"""Anti double-facturation des frais d'étude (régression 2026-07-18).

Bug : une demande de crédit peut rester ``EN_ATTENTE`` alors que ses frais
d'étude sont DÉJÀ réglés (bénéficiaire campagne qui attend encore son carnet).
Toutes les surfaces conditionnaient le paiement au seul statut ``EN_ATTENTE``,
si bien que le membre / l'admin pouvait re-régler les frais → double prélèvement.

On verrouille les 3 canaux serveur qui créent un Payment de frais d'étude :
  * ``/payments/init/`` (mobile money, membre) ;
  * ``/payments/admin/cash-in/`` (saisie agence, admin) ;
  * ``/loans/admin/requests/<pk>/study-fee/`` (enregistrement manuel, admin).

Le canal « déduction épargne » est déjà protégé (``study_fee_due`` renvoie 0),
et le hook ``_hook_loan_request_fees`` ne rapproche plus que les demandes dont
les frais ne sont pas réglés.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType, Payment

pytestmark = pytest.mark.django_db(transaction=True)


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


@pytest.fixture
def request_fees_paid_still_pending(active_member):
    """Demande EN_ATTENTE dont les frais d'étude sont DÉJÀ réglés (cas campagne
    en attente de carnet)."""
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Frais réglés, demande encore en attente du carnet.",
        statut=LoanRequest.Statut.EN_ATTENTE,
        frais_demande_credit_paye=True,
    )


def _count_fee_payments(member):
    return Payment.objects.filter(
        member=member, type=Payment.Type.FRAIS_DEMANDE_CREDIT
    ).count()


class TestNoDoubleChargeStudyFee:
    def test_member_init_blocked_when_already_paid(
        self, active_member, fee_5000, request_fees_paid_still_pending
    ):
        client = APIClient()
        client.force_authenticate(active_member.user)
        resp = client.post(
            "/api/v1/payments/init/",
            {
                "type": "frais_demande_credit",
                "montant": "5000",
                "phone": "237699000000",
                "network": "MTN",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content
        assert _count_fee_payments(active_member) == 0

    def test_admin_cash_in_blocked_when_already_paid(
        self, active_member, admin_user, fee_5000, request_fees_paid_still_pending
    ):
        client = APIClient()
        client.force_authenticate(admin_user)
        resp = client.post(
            "/api/v1/payments/admin/cash-in/",
            {
                "member_id": active_member.id,
                "type": "frais_demande_credit",
                "montant": "5000",
            },
            format="json",
        )
        assert resp.status_code == 400, resp.content
        assert _count_fee_payments(active_member) == 0

    def test_admin_manual_record_blocked_when_already_paid(
        self, active_member, admin_user, fee_5000, request_fees_paid_still_pending
    ):
        client = APIClient()
        client.force_authenticate(admin_user)
        resp = client.post(
            f"/api/v1/loans/requests/{request_fees_paid_still_pending.id}/study-fee/",
            {},
            format="json",
        )
        assert resp.status_code == 400, resp.content
        assert _count_fee_payments(active_member) == 0
