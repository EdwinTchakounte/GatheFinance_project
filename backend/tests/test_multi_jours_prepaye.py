"""LOT 6 (refonte 2026) — Versement multi-jours pré-payé end-to-end.

Couvre :
  - PaymentInitSerializer accepte ``nb_jours_couverts``
  - POST /payments/init/ valide :
      * 1 <= nb <= collecte.prepay.max_days
      * montant == nb × collecte.min_per_day (mode B)
      * nb > 1 refusé pour les autres types que EPARGNE
  - Persistance ``Payment.nb_jours_couverts``
  - Hook ``_hook_savings_deposit`` propage à ``SavingsTransaction``
  - SavingsInfoView expose les paramètres 2026 (min, prepay_max)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.payments.models import Payment
from apps_coop.payments.services import _hook_savings_deposit
from apps_coop.savings.models import SavingsTransaction


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def member_client(active_member):
    """Client DRF authentifié comme l'``active_member`` standard."""
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    return client


_INIT_PATH = "/api/v1/payments/init/"
_INFO_PATH = "/api/v1/savings/info/"


# ---------------------------------------------------------------------------
# Persistance Payment.nb_jours_couverts via API
# ---------------------------------------------------------------------------


class TestPaymentInitPersistsNbJours:

    def test_default_is_one_when_omitted(self, active_member, member_client):
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "1000",
                "phone": "237699000000",
                "network": "MTN",
            },
            format="json",
        )
        # 201 attendu (création du Payment + Tara mock).
        assert resp.status_code in (200, 201), resp.content
        payment = Payment.objects.get(member=active_member)
        assert payment.nb_jours_couverts == 1

    def test_multi_day_value_persisted(self, active_member, member_client):
        # 5 jours × 1000/j = 5000.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "5000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 5,
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.content
        payment = Payment.objects.get(member=active_member)
        assert payment.nb_jours_couverts == 5


# ---------------------------------------------------------------------------
# Validation Mode B (multi-jours)
# ---------------------------------------------------------------------------


class TestModeBValidation:

    def test_amount_must_match_nb_x_min(self, active_member, member_client):
        # 5 jours mais montant 4000 (au lieu de 5000) → 400.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "4000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 5,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert b"montant attendu" in resp.content or b"multi-jours" in resp.content

    def test_nb_above_max_rejected(self, active_member, member_client):
        AppSetting.objects.update_or_create(
            cle="collecte.prepay.max_days", defaults={"valeur": "30"}
        )
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "31000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 31,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert b"plafonn" in resp.content or b"max" in resp.content.lower()

    def test_multi_day_with_custom_min_per_day(
        self, active_member, member_client
    ):
        # Admin a passé la cotisation à 1500/j.
        AppSetting.objects.update_or_create(
            cle="collecte.min_per_day", defaults={"valeur": "1500"}
        )
        # 4 jours × 1500 = 6000.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "6000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 4,
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.content
        # 4 jours × 1500 mais montant 5000 → 400 (incohérent).
        resp_bad = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "5000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 4,
            },
            format="json",
        )
        assert resp_bad.status_code == 400

    def test_multi_day_rejected_for_non_epargne_type(
        self, active_member, member_client
    ):
        # nb > 1 sur un type autre que EPARGNE → 400.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne_classique",
                "montant": "5000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 5,
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_multi_day_accepts_amount_above_min(
        self, active_member, member_client
    ):
        # Montant LIBRE : 5 jours, 10 000 (= 2 000/jour ≥ 1 000) → accepté.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "10000",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 5,
            },
            format="json",
        )
        assert resp.status_code in (200, 201), resp.content
        payment = Payment.objects.get(member=active_member)
        assert payment.montant == Decimal("10000")
        assert payment.nb_jours_couverts == 5

    def test_amount_must_be_multiple_of_step(
        self, active_member, member_client
    ):
        # 5 jours, 10 025 (non multiple de 50) → 400.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "10025",
                "phone": "237699000000",
                "network": "MTN",
                "nb_jours_couverts": 5,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert b"multiple" in resp.content

    def test_single_day_below_min_rejected(
        self, active_member, member_client
    ):
        # 1 jour, 500 (< 1 000/jour) → 400.
        resp = member_client.post(
            _INIT_PATH,
            data={
                "type": "epargne",
                "montant": "500",
                "phone": "237699000000",
                "network": "MTN",
            },
            format="json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Hook _hook_savings_deposit propage nb_jours_couverts
# ---------------------------------------------------------------------------


class TestHookPropagatesNbJours:

    def test_hook_writes_nb_jours_on_savings_transaction(self, active_member):
        from django.utils import timezone

        payment = Payment.objects.create(
            member=active_member,
            montant=Decimal("5000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.VALIDE,
            date_versement=timezone.now(),
            date_validation=timezone.now(),
            nb_jours_couverts=5,
        )
        # Le hook est appelé manuellement (en réel : depuis le webhook Tara).
        from django.db import transaction

        with transaction.atomic():
            _hook_savings_deposit(payment, {})

        tx = SavingsTransaction.objects.get(payment=payment)
        assert tx.nb_jours_couverts == 5
        assert tx.montant == Decimal("5000")


# ---------------------------------------------------------------------------
# SavingsInfoView expose les paramètres collecte 2026
# ---------------------------------------------------------------------------


class TestSavingsInfoExposesRefonte2026:

    def test_default_values_present(self):
        client = APIClient()
        resp = client.get(_INFO_PATH)
        assert resp.status_code == 200
        body = resp.json()
        # Champs 2026 attendus.
        assert "collecte_min_per_day_xaf" in body
        assert body["collecte_min_per_day_xaf"] == 1000
        assert body["collecte_prepay_max_days"] == 30
        assert "collecte_monthly_commission_rate" in body
        assert body["collecte_end_of_month_default"] == "cash"

    def test_respects_admin_overrides(self):
        AppSetting.objects.update_or_create(
            cle="collecte.min_per_day", defaults={"valeur": "2000"}
        )
        AppSetting.objects.update_or_create(
            cle="collecte.prepay.max_days", defaults={"valeur": "60"}
        )
        client = APIClient()
        resp = client.get(_INFO_PATH)
        body = resp.json()
        assert body["collecte_min_per_day_xaf"] == 2000
        assert body["collecte_prepay_max_days"] == 60
