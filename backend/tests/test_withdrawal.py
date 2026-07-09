"""Tests du flow de retrait d'épargne (demande → décision admin).

Couvre :
  • flow PRESENTIEL legacy (defaults — APPROUVEE après décision admin)
  • flow MOMO refonte (init payout Tara, statut EN_PAYOUT → COMPLETEE
    via webhook, ou PAYOUT_FAILED si Tara KO)
  • marquage présentiel (APPROUVEE → COMPLETEE par l'admin)
  • retry payout (PAYOUT_FAILED → relance)
"""
from decimal import Decimal

import pytest

from apps_coop.savings.models import SavingsTransaction, WithdrawalRequest
from apps_coop.savings.services import (
    decide_withdrawal,
    mark_withdrawal_paid,
    request_withdrawal,
    retry_withdrawal_payout,
)


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


# ────────────────────────────────────────────────────────────────────────────
# Refonte 2026 — Canal MOMO / Présentiel + payout Tara automatique
# ────────────────────────────────────────────────────────────────────────────


class TestRequestWithdrawalMomo:
    """Validation des nouveaux champs `mode_paiement` / `recipient_phone` /
    `network` au moment de la création par le membre."""

    def test_create_momo_with_phone_and_network(self, active_member):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000001",
            network="MTN",
        )
        assert wr.mode_paiement == WithdrawalRequest.ModePaiement.MOMO
        assert wr.recipient_phone == "690000001"
        assert wr.network == "MTN"
        assert wr.statut == WithdrawalRequest.Statut.EN_ATTENTE

    def test_momo_requires_phone(self, active_member):
        acc = _fund(active_member, "50000")
        with pytest.raises(ValueError, match="(?i)numéro mobile money"):
            request_withdrawal(
                acc,
                montant=Decimal("10000"),
                mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
                recipient_phone="",
                network="MTN",
            )

    def test_momo_requires_known_network(self, active_member):
        acc = _fund(active_member, "50000")
        with pytest.raises(ValueError, match="(?i)réseau mobile money invalide"):
            request_withdrawal(
                acc,
                montant=Decimal("10000"),
                mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
                recipient_phone="690000001",
                network="BITCOIN",
            )

    def test_presentiel_clears_phone_and_network(self, active_member):
        """En PRÉSENTIEL on ignore (et vide) phone/network même si fournis."""
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
            recipient_phone="690000001",  # ignoré
            network="MTN",                 # ignoré
        )
        assert wr.recipient_phone == ""
        assert wr.network == ""


class TestDecideWithdrawalMomo:
    """À l'approbation d'un retrait MOMO : débit du solde + init payout Tara.

    Tara est en mode mock (pas de TARA_API_KEY) → le payout renvoie une
    référence ``MOCK-PAYOUT-*`` sans appel réseau, ce qui simule un succès
    init côté provider. Le webhook sera testé séparément.
    """

    @pytest.fixture(autouse=True)
    def _tara(self, tara_payout_on):
        pass

    def test_approve_momo_creates_payment_and_moves_to_en_payout(
        self, active_member, admin_user
    ):
        from apps_coop.payments.models import Payment

        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("15000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000001",
            network="ORANGE",
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        acc.refresh_from_db()

        # Solde débité (commit à l'approbation, comme pour le présentiel)
        assert acc.solde == Decimal("35000.00")
        # Statut bascule MOMO en cours
        assert wr.statut == WithdrawalRequest.Statut.EN_PAYOUT
        # Payment payout créé et lié
        assert wr.payout_payment_id is not None
        p = Payment.objects.get(pk=wr.payout_payment_id)
        assert p.type == Payment.Type.DECAISSEMENT
        assert p.source == Payment.Source.MOBILE_MONEY
        assert p.statut == Payment.Statut.EN_ATTENTE
        assert p.reference_externe.startswith("MOCK-PAYOUT-")  # mock provider

    def test_webhook_decaissement_completes_withdrawal(
        self, active_member, admin_user
    ):
        """Le webhook Tara marque le Payment `valide`, ce qui doit basculer
        la WithdrawalRequest en `COMPLETEE` via `_hook_decaissement`."""
        from apps_coop.payments.models import Payment
        from apps_coop.payments.services import handle_webhook_event

        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("12000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000002",
            network="MTN",
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.EN_PAYOUT
        payment_id = wr.payout_payment_id

        # Simule le webhook Tara "SUCCESS" sur ce Payment.
        payment = Payment.objects.get(pk=payment_id)
        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference=payment.reference_externe,
            raw_payload={"mocked": True},
        )

        wr.refresh_from_db()
        payment.refresh_from_db()
        assert payment.statut == Payment.Statut.VALIDE
        assert wr.statut == WithdrawalRequest.Statut.COMPLETEE

    def test_payout_failure_marks_payout_failed_and_keeps_debit(
        self, active_member, admin_user, monkeypatch
    ):
        """Quand `provider.init_payout` lève ProviderError, le statut WR doit
        passer à `PAYOUT_FAILED` et le solde reste débité (pas de rollback
        du débit — l'admin pourra retry sans re-débiter)."""
        from apps_coop.payments.providers import tara as tara_mod
        from apps_coop.payments.providers.base import ProviderError

        def boom(self, payment, *, recipient_phone, network):
            raise ProviderError("Tara down", retryable=True)

        monkeypatch.setattr(tara_mod.TaraProvider, "init_payout", boom)

        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("20000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000003",
            network="MTN",
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        acc.refresh_from_db()

        assert wr.statut == WithdrawalRequest.Statut.PAYOUT_FAILED
        assert "Tara down" in wr.motif_rejet
        # Solde toujours débité — l'admin retentera (ou remboursera manuellement)
        assert acc.solde == Decimal("30000.00")


class TestMarkWithdrawalPaid:
    """Flow PRÉSENTIEL : l'admin clique 'Confirmer remise espèces'."""

    def test_mark_paid_moves_approved_to_completee(
        self, active_member, admin_user
    ):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.APPROUVEE

        mark_withdrawal_paid(wr, agent=admin_user, note="Cash remis comptoir 3")
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.COMPLETEE
        assert wr.handed_over_by_id == admin_user.id
        assert wr.handed_over_at is not None

    def test_mark_paid_works_for_momo_when_tara_off(self, active_member, admin_user):
        # Payout Tara désactivé (défaut) → un retrait MOMO approuvé reste
        # APPROUVEE (l'admin fait le virement sur Tara), puis on le marque payé.
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000004",
            network="MTN",
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.APPROUVEE
        wr = mark_withdrawal_paid(wr, agent=admin_user, note="Viré sur Tara")
        assert wr.statut == WithdrawalRequest.Statut.COMPLETEE

    def test_mark_paid_idempotent(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        mark_withdrawal_paid(wr, agent=admin_user)
        first_at = wr.handed_over_at

        wr.refresh_from_db()
        mark_withdrawal_paid(wr, agent=admin_user)  # 2e appel → idempotent
        wr.refresh_from_db()
        assert wr.handed_over_at == first_at  # pas écrasé


class TestRetryWithdrawalPayout:
    """Réessai d'un payout MOMO échoué."""

    @pytest.fixture(autouse=True)
    def _tara(self, tara_payout_on):
        pass

    def test_retry_recreates_payment_and_moves_to_en_payout(
        self, active_member, admin_user, monkeypatch
    ):
        from apps_coop.payments.providers import tara as tara_mod
        from apps_coop.payments.providers.base import ProviderError

        calls = {"n": 0}

        def flaky(self, payment, *, recipient_phone, network):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ProviderError("Tara timeout", retryable=True)
            # 2e essai : succès
            from apps_coop.payments.providers.base import PayoutResult
            return PayoutResult(
                provider_reference=f"OK-PAYOUT-{payment.idempotency_key}",
                raw={"retry": True},
            )

        monkeypatch.setattr(tara_mod.TaraProvider, "init_payout", flaky)

        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            recipient_phone="690000005",
            network="MTN",
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.PAYOUT_FAILED

        # Retry — 2e appel Tara qui réussit
        retry_withdrawal_payout(wr, agent=admin_user)
        wr.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.EN_PAYOUT
        assert wr.payout_payment.reference_externe.startswith("OK-PAYOUT-")
        assert calls["n"] == 2  # init_payout effectivement réessayé

    def test_retry_rejects_non_failed(self, active_member, admin_user):
        acc = _fund(active_member, "50000")
        wr = request_withdrawal(
            acc,
            montant=Decimal("10000"),
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)
        wr.refresh_from_db()
        with pytest.raises(ValueError, match="(?i)momo"):
            retry_withdrawal_payout(wr, agent=admin_user)


class TestWithdrawalEndpointsMomo:
    """Endpoints HTTP — création MOMO côté membre + mark-paid côté admin."""

    def test_member_create_momo_via_api(self, client, active_member):
        _fund(active_member, "40000")
        client.force_login(active_member.user)
        r = client.post(
            "/api/v1/savings/withdrawal/",
            data={
                "montant": "8000",
                "motif": "Réparation moto",
                "mode_paiement": "momo",
                "recipient_phone": "690123456",
                "network": "MTN",
            },
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["mode_paiement"] == "momo"
        assert body["recipient_phone_masked"] == "6901***56"
        assert body["network"] == "MTN"

    def test_member_create_momo_missing_phone_returns_400(self, client, active_member):
        _fund(active_member, "40000")
        client.force_login(active_member.user)
        r = client.post(
            "/api/v1/savings/withdrawal/",
            data={
                "montant": "8000",
                "mode_paiement": "momo",
                # phone absent
                "network": "MTN",
            },
            content_type="application/json",
        )
        assert r.status_code == 400
        assert "recipient_phone" in r.json()

    def test_admin_mark_paid_endpoint(self, client, active_member, admin_user):
        _fund(active_member, "30000")
        client.force_login(active_member.user)
        r = client.post(
            "/api/v1/savings/withdrawal/",
            data={"montant": "10000", "mode_paiement": "presentiel"},
            content_type="application/json",
        )
        wid = r.json()["id"]

        client.force_login(admin_user)
        client.post(
            f"/api/v1/admin/withdrawals/{wid}/decide/",
            data={"decision": "approuvee"},
            content_type="application/json",
        )

        rmp = client.post(
            f"/api/v1/admin/withdrawals/{wid}/mark-paid/",
            data={"note": "Cash remis comptoir 1"},
            content_type="application/json",
        )
        assert rmp.status_code == 200, rmp.content
        assert rmp.json()["statut"] == "completee"
