"""Restitution « versement Mobile Money » de la clôture collecte (§4 refonte 2026).

Le membre choisit la préférence ``mobile_money`` et renseigne sa destination
(``payout_phone`` + ``payout_network``). À la clôture :

  - **Par défaut** (``collecte.monthly.cash_payout`` OFF) : versement MANUEL par
    la coopérative → une ``WithdrawalRequest(MOMO, APPROUVEE)`` est déposée dans
    la file de payout admin. La coop transfère à la main puis marque « payé ».
  - **Automatisation ON** : décaissement automatique (Tara). En mock mode (pas de
    clé), ``init_payout`` renvoie une référence ``MOCK-PAYOUT-…`` sans réseau.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import (
    SavingsAccount,
    SavingsTransaction,
    WithdrawalRequest,
)
from apps_coop.savings.tasks import collecte_fin_de_mois


pytestmark = pytest.mark.django_db(transaction=True)


def _prime(
    member,
    montant="100000",
    *,
    phone="+237690000000",
    network="MTN",
    auto="false",
    preference=SavingsAccount.EndOfMonthPreference.MOBILE_MONEY,
):
    AppSetting.objects.update_or_create(
        cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
    )
    AppSetting.objects.update_or_create(
        cle="collecte.monthly.cash_payout", defaults={"valeur": auto}
    )
    acc = member.savings_account
    acc.solde = Decimal(montant)
    acc.end_of_month_preference = preference
    acc.payout_phone = phone or ""
    acc.payout_network = network or ""
    acc.save(
        update_fields=[
            "solde",
            "end_of_month_preference",
            "payout_phone",
            "payout_network",
        ]
    )
    return acc


def _payout(member):
    return Payment.objects.filter(
        member=member,
        type=Payment.Type.DECAISSEMENT,
        source=Payment.Source.MOBILE_MONEY,
    ).first()


def _payout_request(member):
    return WithdrawalRequest.objects.filter(
        account=member.savings_account,
        mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
    ).first()


class TestManualPayoutDefault:
    """Défaut = versement manuel par la coop (aucun décaissement auto)."""

    def test_mobile_money_queues_approved_withdrawal_request(self, active_member):
        _prime(active_member, "100000")  # net 99 000 après 1 %
        collecte_fin_de_mois()

        wr = _payout_request(active_member)
        assert wr is not None
        assert wr.statut == WithdrawalRequest.Statut.APPROUVEE
        assert wr.montant == Decimal("99000.00")
        assert wr.recipient_phone == "+237690000000"
        assert wr.network == "MTN"
        assert wr.source == WithdrawalRequest.Source.COLLECTE
        # Lié à la ligne de restitution déjà écrite (pas de double débit).
        restitution = SavingsTransaction.objects.get(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.RESTITUTION_CASH,
        )
        assert wr.transaction_id == restitution.id
        # Aucun décaissement automatique.
        assert _payout(active_member) is None
        assert AuditLog.objects.filter(
            action="collecte.momo_restitution_queued"
        ).exists()

    def test_cash_preference_never_queues_payout(self, active_member):
        acc = _prime(
            active_member,
            preference=SavingsAccount.EndOfMonthPreference.CASH,
        )
        acc.save(update_fields=["end_of_month_preference"])
        collecte_fin_de_mois()
        # Choix « agence » : simple ligne au grand livre, pas de payout.
        assert _payout_request(active_member) is None
        assert _payout(active_member) is None

    def test_epargne_preference_never_queues_payout(self, active_member):
        acc = _prime(
            active_member,
            preference=SavingsAccount.EndOfMonthPreference.EPARGNE,
        )
        acc.save(update_fields=["end_of_month_preference"])
        collecte_fin_de_mois()
        assert _payout_request(active_member) is None

    def test_no_destination_skips_and_audits(self, active_member):
        _prime(active_member, phone="", network="")
        # member.phone doit aussi être vide pour vraiment sauter.
        active_member.phone = ""
        active_member.save(update_fields=["phone"])
        collecte_fin_de_mois()
        assert _payout_request(active_member) is None
        assert AuditLog.objects.filter(
            action="collecte.momo_restitution_skipped"
        ).exists()


class TestAutoTaraPayout:
    """Automatisation ON → décaissement Tara (comme un retrait MOMO)."""

    def test_payout_created_for_net_amount_and_linked(self, active_member):
        _prime(active_member, "100000", auto="true")
        collecte_fin_de_mois()

        payment = _payout(active_member)
        assert payment is not None
        assert payment.montant == Decimal("99000.00")
        assert payment.reference_externe.startswith("MOCK-PAYOUT-")
        restitution = SavingsTransaction.objects.get(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.RESTITUTION_CASH,
        )
        assert restitution.payment_id == payment.id
        assert AuditLog.objects.filter(
            action="collecte.cash_payout_initiated"
        ).exists()

    def test_webhook_completion_is_recognized_not_orphan(self, active_member):
        _prime(active_member, "100000", auto="true")
        collecte_fin_de_mois()
        payment = _payout(active_member)
        assert payment is not None

        if payment.statut == Payment.Statut.EN_ATTENTE:
            handle_webhook_event(
                payment.idempotency_key,
                "valide",
                provider_reference=payment.reference_externe,
                raw_payload={"test": True},
            )
        payment.refresh_from_db()
        assert payment.statut == Payment.Statut.VALIDE
        assert AuditLog.objects.filter(
            action="collecte.cash_payout_completed"
        ).exists()


class TestIdempotence:
    def test_second_run_same_month_no_double_request(self, active_member):
        _prime(active_member, "100000")
        collecte_fin_de_mois()
        collecte_fin_de_mois()  # 2e passage même mois
        assert (
            WithdrawalRequest.objects.filter(
                account=active_member.savings_account,
                mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
            ).count()
            == 1
        )
