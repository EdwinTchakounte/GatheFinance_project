"""Plancher de dépôt épargne classique — minimum réglementaire 1 000 XAF.

Règle produit (2026) : tout versement, quel que soit le type (cotisation
collecte OU épargne classique), a un minimum de 1 000 XAF. La config admin
``ClassicSavingsConfig.depot_min`` ne peut que RELEVER ce plancher, jamais
l'abaisser sous 1 000.

Validation faite dans ``apps_coop.payments.views.init_payment``.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment
from apps_coop.savings.models import ClassicSavingsConfig


pytestmark = pytest.mark.django_db(transaction=True)

_INIT_PATH = "/api/v1/payments/init/"


@pytest.fixture
def member_client(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    return client


def _post(client, montant: str):
    return client.post(
        _INIT_PATH,
        data={
            "type": "epargne_classique",
            "montant": montant,
            "phone": "237699000000",
            "network": "MTN",
        },
        format="json",
    )


class TestClassicSavingsMinFloor:
    def test_below_1000_rejected_even_when_config_min_is_zero(self, member_client):
        # depot_min par défaut = 0 → le plancher 1 000 doit quand même s'appliquer.
        cfg = ClassicSavingsConfig.get_solo()
        cfg.depot_min = Decimal("0")
        cfg.save()

        resp = _post(member_client, "500")
        assert resp.status_code == 400, resp.content
        assert "1000" in resp.content.decode()
        # Aucun Payment de dépôt créé (le membre porte déjà un Payment
        # frais_carnet issu de son activation — on ne compte que le dépôt).
        assert not Payment.objects.filter(
            type=Payment.Type.EPARGNE_CLASSIQUE
        ).exists()

    def test_exactly_1000_accepted(self, active_member, member_client):
        cfg = ClassicSavingsConfig.get_solo()
        cfg.depot_min = Decimal("0")
        cfg.save()

        resp = _post(member_client, "1000")
        assert resp.status_code in (200, 201), resp.content
        assert Payment.objects.filter(member=active_member).exists()

    def test_admin_can_raise_floor_above_1000(self, member_client):
        # Si l'admin fixe un minimum supérieur, c'est LUI qui prime (5 000).
        cfg = ClassicSavingsConfig.get_solo()
        cfg.depot_min = Decimal("5000")
        cfg.save()

        resp = _post(member_client, "1000")
        assert resp.status_code == 400, resp.content
        assert "5000" in resp.content.decode()
