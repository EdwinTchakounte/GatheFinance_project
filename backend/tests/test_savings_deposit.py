"""Tests du flux dépôt épargne — UC2.

Couvre le hook ``_hook_savings_deposit`` :
  - crédit du SavingsAccount (solde += montant)
  - création de la SavingsTransaction (type=depot, montant correct)
  - idempotence : double webhook sur le même Payment n'incrémente pas 2 fois
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import SavingsAccount, SavingsTransaction


pytestmark = pytest.mark.django_db


class TestSavingsDepositHook:
    def test_valid_deposit_credits_account_and_logs_transaction(self, active_member):
        account = SavingsAccount.objects.get(member=active_member)
        assert account.solde == 0

        payment = Payment.objects.create(
            member=active_member,
            montant=Decimal("25000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code="tara",
            date_versement=timezone.now(),
        )

        handle_webhook_event(payment.idempotency_key, "valide", provider_reference="TX-1", raw_payload={})

        account.refresh_from_db()
        assert account.solde == Decimal("25000")
        # Une seule transaction de type `depot`, montant correct
        tx = SavingsTransaction.objects.get(account=account)
        assert tx.type_op == SavingsTransaction.TypeOp.DEPOT
        assert tx.montant == Decimal("25000")
        assert tx.solde_apres == Decimal("25000")

    def test_idempotent_double_webhook_does_not_double_credit(self, active_member):
        payment = Payment.objects.create(
            member=active_member,
            montant=Decimal("10000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code="tara",
            date_versement=timezone.now(),
        )

        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})
        # Tara renvoie le même event → on doit no-op
        handle_webhook_event(payment.idempotency_key, "valide", raw_payload={})

        account = SavingsAccount.objects.get(member=active_member)
        assert account.solde == Decimal("10000")
        assert SavingsTransaction.objects.filter(account=account).count() == 1
