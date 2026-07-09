"""Frais d'étude de dossier : le montant est PILOTÉ PAR L'ADMIN, jamais le client.

Régression : le mobile envoyait un montant de test (100 XAF éditable). Le backend
doit écraser tout montant client par le tarif officiel (FeeType.DEMANDE_CREDIT)
dès qu'il est configuré (> 0) — sinon un client falsifié réglerait n'importe quoi.
Validation dans ``apps_coop.payments.views.init_payment``.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.payments.models import FeeType, Payment

pytestmark = pytest.mark.django_db(transaction=True)

_INIT = "/api/v1/payments/init/"


@pytest.fixture
def member_client(active_member):
    c = APIClient()
    c.force_authenticate(user=active_member.user)
    return c


def _set_fee(montant: str) -> None:
    fee, _ = FeeType.objects.get_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Frais de demande de crédit"},
    )
    fee.montant = Decimal(montant)
    fee.actif = True
    fee.save()


def _post(client, montant: str):
    return client.post(
        _INIT,
        data={
            "type": "frais_demande_credit",
            "montant": montant,
            "phone": "237699000000",
            "network": "MTN",
        },
        format="json",
    )


def _latest_fee_payment(member):
    return (
        Payment.objects.filter(
            member=member, type=Payment.Type.FRAIS_DEMANDE_CREDIT
        )
        .latest("id")
    )


class TestStudyFeeAuthoritative:
    def test_client_amount_is_overridden_by_feetype(self, active_member, member_client):
        _set_fee("5000")
        # Le client tente 100 XAF (reliquat de test) → doit être écrasé à 5000.
        resp = _post(member_client, "100")
        assert resp.status_code in (200, 201), resp.content
        assert _latest_fee_payment(active_member).montant == Decimal("5000")

    def test_zero_fee_keeps_client_amount(self, active_member, member_client):
        # Étude gratuite / non tarifée (0) → pas d'écrasement.
        _set_fee("0")
        resp = _post(member_client, "100")
        assert resp.status_code in (200, 201), resp.content
        assert _latest_fee_payment(active_member).montant == Decimal("100")
