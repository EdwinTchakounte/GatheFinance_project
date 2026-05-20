"""Tests du flow de retrait d'épargne (demande → décision admin)."""
from decimal import Decimal

import pytest

from apps_coop.savings.models import SavingsTransaction, WithdrawalRequest
from apps_coop.savings.services import decide_withdrawal, request_withdrawal


pytestmark = pytest.mark.django_db(transaction=True)


def _fund(member, amount):
    acc = member.savings_account
    acc.solde = Decimal(amount)
    acc.save(update_fields=["solde"])
    return acc


class TestRequestWithdrawal:
    def test_creates_pending_request(self, active_member):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(acc, montant=Decimal("20000"), motif="Urgence")
        assert wr.statut == WithdrawalRequest.Statut.EN_ATTENTE
        assert wr.montant == Decimal("20000")

    def test_rejects_amount_above_balance(self, active_member):
        acc = _fund(active_member, "10000")
        with pytest.raises(ValueError, match="(?i)supérieur au solde"):
            request_withdrawal(acc, montant=Decimal("20000"))

    def test_rejects_non_positive(self, active_member):
        acc = _fund(active_member, "10000")
        with pytest.raises(ValueError, match="(?i)positif"):
            request_withdrawal(acc, montant=Decimal("0"))

    def test_rejects_double_pending(self, active_member):
        acc = _fund(active_member, "50000")
        request_withdrawal(acc, montant=Decimal("1000"))
        with pytest.raises(ValueError, match="(?i)déjà en attente"):
            request_withdrawal(acc, montant=Decimal("2000"))


class TestDecideWithdrawal:
    def test_approve_debits_balance_and_creates_tx(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(acc, montant=Decimal("20000"))

        decide_withdrawal(wr, decided_by=admin_user, approve=True)

        wr.refresh_from_db()
        acc.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.APPROUVEE
        assert acc.solde == Decimal("30000.00")
        assert wr.transaction is not None
        tx = SavingsTransaction.objects.get(pk=wr.transaction_id)
        assert tx.type_op == SavingsTransaction.TypeOp.RETRAIT
        assert tx.montant == Decimal("20000")
        assert tx.solde_apres == Decimal("30000.00")

    def test_reject_requires_motif(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(acc, montant=Decimal("20000"))
        with pytest.raises(ValueError, match="(?i)motif"):
            decide_withdrawal(wr, decided_by=admin_user, approve=False, motif_rejet="")

    def test_reject_sets_status_no_debit(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(acc, montant=Decimal("20000"))
        decide_withdrawal(wr, decided_by=admin_user, approve=False, motif_rejet="Solde de garantie")
        wr.refresh_from_db()
        acc.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.REJETEE
        assert acc.solde == Decimal("50000")  # inchangé

    def test_idempotent_decide(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(acc, montant=Decimal("20000"))
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        # 2e appel : ne re-débite pas
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        acc.refresh_from_db()
        assert acc.solde == Decimal("30000.00")


class TestWithdrawalEndpoints:
    def test_member_creates_then_admin_approves(self, client, active_member, admin_user):
        _fund(active_member, "40000")
        client.force_login(active_member.user)
        r = client.post(
            "/api/v1/savings/withdrawal/",
            data={"montant": "15000", "motif": "Frais scolaires"},
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        wid = r.json()["id"]

        client.force_login(admin_user)
        rd = client.post(
            f"/api/v1/admin/withdrawals/{wid}/decide/",
            data={"decision": "approuvee"},
            content_type="application/json",
        )
        assert rd.status_code == 200, rd.content
        assert rd.json()["statut"] == "approuvee"

        active_member.savings_account.refresh_from_db()
        assert active_member.savings_account.solde == Decimal("25000.00")
