"""W2 — alerte staff à la soumission d'un retrait.

Quand ``notifications.ops_email`` est renseigné, une demande de retrait émet
l'événement ``withdrawal.admin_pending`` vers cette adresse (to_email). Vide =
aucun mail staff (mais le membre garde son accusé de réception).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.savings.models import ClassicSavingsAccount, WithdrawalRequest
from apps_coop.savings.services import request_withdrawal

pytestmark = pytest.mark.django_db


def _classic(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


def _set_ops(email: str):
    AppSetting.objects.update_or_create(
        cle="notifications.ops_email", defaults={"valeur": email, "description": ""}
    )


class TestWithdrawalStaffAlert:
    def test_staff_alert_emitted_when_ops_email_set(self, active_member):
        _set_ops("ops@test.local")
        cacc = _classic(active_member, "80000")
        with patch("apps_coop.notifications.events.emit_event") as mock_emit:
            request_withdrawal(
                montant=Decimal("20000"),
                source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
                classic_account=cacc,
            )
        codes = [c.args[0] for c in mock_emit.call_args_list]
        assert "withdrawal.admin_pending" in codes
        staff_call = next(
            c for c in mock_emit.call_args_list if c.args[0] == "withdrawal.admin_pending"
        )
        assert staff_call.kwargs.get("to_email") == "ops@test.local"

    def test_no_staff_alert_when_ops_email_empty(self, active_member):
        _set_ops("")
        cacc = _classic(active_member, "80000")
        with patch("apps_coop.notifications.events.emit_event") as mock_emit:
            request_withdrawal(
                montant=Decimal("20000"),
                source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
                classic_account=cacc,
            )
        codes = [c.args[0] for c in mock_emit.call_args_list]
        assert "withdrawal.admin_pending" not in codes
