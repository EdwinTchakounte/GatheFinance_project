"""Tests du socle « coûts modifiables » (BR2) — RateParam + get_rate + API.

Couvre :
  - le getter ``get_rate`` : fallback réglementaire quand pas de ligne DB,
    valeur DB quand présente, KeyError sur code inconnu ;
  - la commande ``seed_rates`` (création + idempotence) ;
  - les endpoints : GET taux (membre), GET config admin (staff),
    PATCH frais/taux (staff) avec validations + protection d'accès.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps_coop.payments.models import FeeType, RateParam
from apps_coop.payments.rates import default_rate, get_rate


class TestGetRate:
    def test_fallback_to_regulation_default_when_no_row(self, db):
        # Aucune ligne RateParam → on retombe sur le défaut réglementaire.
        assert RateParam.objects.count() == 0
        assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.10")
        assert get_rate(RateParam.Code.SAVINGS_INTEREST_MONTHLY) == Decimal("0.01")
        assert get_rate(RateParam.Code.LATE_PENALTY) == Decimal("0.50")

    def test_reads_db_value_when_present(self, db):
        RateParam.objects.create(
            code=RateParam.Code.LOAN_INTEREST, libelle="x", valeur=Decimal("0.20")
        )
        assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.20")

    def test_inactive_row_falls_back_to_default(self, db):
        RateParam.objects.create(
            code=RateParam.Code.LOAN_INTEREST,
            libelle="x",
            valeur=Decimal("0.20"),
            actif=False,
        )
        assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.10")

    def test_unknown_code_raises(self, db):
        with pytest.raises(KeyError):
            get_rate("NOPE")
        with pytest.raises(KeyError):
            default_rate("NOPE")


class TestSeedRates:
    def test_creates_all_codes_with_regulation_values(self, db):
        call_command("seed_rates")
        assert RateParam.objects.count() == len(RateParam.Code.values)
        loan = RateParam.objects.get(code=RateParam.Code.LOAN_INTEREST)
        assert loan.valeur == Decimal("0.10")

    def test_idempotent_keeps_admin_edits(self, db):
        call_command("seed_rates")
        loan = RateParam.objects.get(code=RateParam.Code.LOAN_INTEREST)
        loan.valeur = Decimal("0.25")
        loan.save(update_fields=["valeur"])
        # Re-seed ne doit PAS écraser la valeur éditée par l'admin.
        call_command("seed_rates")
        loan.refresh_from_db()
        assert loan.valeur == Decimal("0.25")
        assert RateParam.objects.count() == len(RateParam.Code.values)


class TestRatesEndpoints:
    def test_member_can_read_rates(self, client, active_member):
        call_command("seed_rates")
        client.force_login(active_member.user)
        r = client.get("/api/v1/payments/rates/")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["LOAN_INTEREST"]["valeur"] == "0.1000"

    def test_anonymous_cannot_read_rates(self, client, db):
        r = client.get("/api/v1/payments/rates/")
        assert r.status_code in (401, 403)

    def test_admin_config_returns_fees_and_rates(self, client, admin_user):
        call_command("seed_fees")
        call_command("seed_rates")
        client.force_login(admin_user)
        r = client.get("/api/v1/payments/admin/config/")
        assert r.status_code == 200, r.content
        body = r.json()
        assert "fees" in body and "rates" in body
        assert any(f["code"] == "ADHESION" for f in body["fees"])
        assert any(rt["code"] == "LOAN_INTEREST" for rt in body["rates"])

    def test_member_cannot_read_admin_config(self, client, active_member):
        client.force_login(active_member.user)
        r = client.get("/api/v1/payments/admin/config/")
        assert r.status_code == 403


class TestUpdateRate:
    def test_admin_updates_rate_and_get_rate_reflects_it(self, client, admin_user):
        call_command("seed_rates")
        client.force_login(admin_user)
        r = client.patch(
            "/api/v1/payments/admin/rates/LOAN_INTEREST/",
            data=json.dumps({"valeur": "0.12"}),
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        assert get_rate(RateParam.Code.LOAN_INTEREST) == Decimal("0.12")

    def test_rejects_rate_out_of_range(self, client, admin_user):
        call_command("seed_rates")
        client.force_login(admin_user)
        r = client.patch(
            "/api/v1/payments/admin/rates/LOAN_INTEREST/",
            data=json.dumps({"valeur": "1.5"}),
            content_type="application/json",
        )
        assert r.status_code == 400, r.content

    def test_unknown_rate_code_404(self, client, admin_user):
        client.force_login(admin_user)
        r = client.patch(
            "/api/v1/payments/admin/rates/NOPE/",
            data=json.dumps({"valeur": "0.1"}),
            content_type="application/json",
        )
        assert r.status_code == 404

    def test_member_cannot_update_rate(self, client, active_member):
        call_command("seed_rates")
        client.force_login(active_member.user)
        r = client.patch(
            "/api/v1/payments/admin/rates/LOAN_INTEREST/",
            data=json.dumps({"valeur": "0.12"}),
            content_type="application/json",
        )
        assert r.status_code == 403


class TestUpdateFee:
    def test_admin_updates_fee_montant(self, client, admin_user):
        call_command("seed_fees")
        client.force_login(admin_user)
        r = client.patch(
            "/api/v1/payments/admin/fees/ADHESION/",
            data=json.dumps({"montant": "12000"}),
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        fee = FeeType.objects.get(code=FeeType.Code.ADHESION)
        assert fee.montant == Decimal("12000")

    def test_rejects_negative_montant(self, client, admin_user):
        call_command("seed_fees")
        client.force_login(admin_user)
        r = client.patch(
            "/api/v1/payments/admin/fees/ADHESION/",
            data=json.dumps({"montant": "-5"}),
            content_type="application/json",
        )
        assert r.status_code == 400, r.content

    def test_member_cannot_update_fee(self, client, active_member):
        call_command("seed_fees")
        client.force_login(active_member.user)
        r = client.patch(
            "/api/v1/payments/admin/fees/ADHESION/",
            data=json.dumps({"montant": "12000"}),
            content_type="application/json",
        )
        assert r.status_code == 403
