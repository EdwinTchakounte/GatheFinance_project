"""Restitution « cash » de la clôture collecte → payout Mobile Money (Tara).

Gated par l'AppSetting ``collecte.monthly.cash_payout`` (défaut OFF). En mock
mode (pas de clé Tara en test), ``init_payout`` renvoie une référence
``MOCK-PAYOUT-…`` sans appel réseau.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import SavingsAccount, SavingsTransaction
from apps_coop.savings.tasks import collecte_fin_de_mois


pytestmark = pytest.mark.django_db(transaction=True)


def _prime(member, montant="100000", *, phone="+237690000000", payout="true"):
    AppSetting.objects.update_or_create(
        cle="collecte.monthly.commission_rate", defaults={"valeur": "0.01"}
    )
    AppSetting.objects.update_or_create(
        cle="collecte.monthly.cash_payout", defaults={"valeur": payout}
    )
    if phone is not None:
        member.phone = phone
        member.save(update_fields=["phone"])
    acc = member.savings_account
    acc.solde = Decimal(montant)
    acc.end_of_month_preference = SavingsAccount.EndOfMonthPreference.CASH
    acc.save(update_fields=["solde", "end_of_month_preference"])
    return acc


def _payout(member):
    return Payment.objects.filter(
        member=member,
        type=Payment.Type.DECAISSEMENT,
        source=Payment.Source.MOBILE_MONEY,
    ).first()


class TestCashPayoutGating:
    def test_disabled_by_default_no_payout(self, active_member):
        _prime(active_member, payout="false")
        collecte_fin_de_mois()
        assert _payout(active_member) is None  # aucune sortie d'argent

    def test_epargne_preference_never_pays_out(self, active_member):
        acc = _prime(active_member)
        acc.end_of_month_preference = SavingsAccount.EndOfMonthPreference.EPARGNE
        acc.save(update_fields=["end_of_month_preference"])
        collecte_fin_de_mois()
        assert _payout(active_member) is None

    def test_no_phone_skips_and_audits(self, active_member):
        _prime(active_member, phone="")
        collecte_fin_de_mois()
        assert _payout(active_member) is None
        assert AuditLog.objects.filter(
            action="collecte.cash_payout_skipped"
        ).exists()


class TestCashPayoutInitiation:
    def test_payout_created_for_net_amount_and_linked(self, active_member):
        _prime(active_member, "100000")  # net 99 000 après 1 %
        collecte_fin_de_mois()

        payment = _payout(active_member)
        assert payment is not None
        assert payment.montant == Decimal("99000.00")
        assert payment.provider_code  # provider résolu
        assert payment.reference_externe.startswith("MOCK-PAYOUT-")
        assert payment.statut in (
            Payment.Statut.EN_ATTENTE,
            Payment.Statut.VALIDE,
        )
        # La restitution cash est liée au payout (finalisation webhook propre).
        restitution = SavingsTransaction.objects.get(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.RESTITUTION_CASH,
        )
        assert restitution.payment_id == payment.id
        assert AuditLog.objects.filter(
            action="collecte.cash_payout_initiated"
        ).exists()

    def test_webhook_completion_is_recognized_not_orphan(self, active_member):
        _prime(active_member, "100000")
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
        # Reconnu comme restitution collecte (pas « orphelin »).
        assert AuditLog.objects.filter(
            action="collecte.cash_payout_completed"
        ).exists()


class TestCashPayoutIdempotence:
    def test_second_run_same_month_no_double_payout(self, active_member):
        _prime(active_member, "100000")
        collecte_fin_de_mois()
        collecte_fin_de_mois()  # 2e passage même mois
        assert (
            Payment.objects.filter(
                member=active_member,
                type=Payment.Type.DECAISSEMENT,
                source=Payment.Source.MOBILE_MONEY,
            ).count()
            == 1
        )
