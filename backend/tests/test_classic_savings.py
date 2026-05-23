"""Module Épargne classique — dissocié de la cotisation journalière.

Couvre :
  - config singleton (défauts neutres, get_solo)
  - dépôt validé → crédite le compte épargne classique (pas le compte cotisation)
  - dissociation : le dépôt classique ne touche pas SavingsAccount (cotisation)
  - endpoint membre GET /savings/classic/me/ (création paresseuse)
  - endpoint staff GET/PATCH /savings/classic/config/
  - garde-fous d'init (produit inactif, dépôt sous le minimum)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsConfig,
    ClassicSavingsTransaction,
    SavingsAccount,
)


pytestmark = pytest.mark.django_db


def _confirm_classic_deposit(member, montant) -> Payment:
    p = Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.EPARGNE_CLASSIQUE,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
    )
    handle_webhook_event(p.idempotency_key, "valide", provider_reference="REF")
    return p


class TestConfig:
    def test_get_solo_creates_with_neutral_defaults(self):
        cfg = ClassicSavingsConfig.get_solo()
        assert cfg.pk == ClassicSavingsConfig.SINGLETON_PK
        assert cfg.actif is True
        assert cfg.taux_interet_mensuel == Decimal("0")  # règles à définir
        assert cfg.depot_max is None
        # idempotent
        assert ClassicSavingsConfig.get_solo().pk == cfg.pk
        assert ClassicSavingsConfig.objects.count() == 1


class TestDeposit:
    def test_deposit_credits_classic_account(self, active_member):
        _confirm_classic_deposit(active_member, Decimal("25000"))

        acc = ClassicSavingsAccount.objects.get(member=active_member)
        assert acc.solde == Decimal("25000")
        tx = ClassicSavingsTransaction.objects.get(account=acc)
        assert tx.type_op == ClassicSavingsTransaction.TypeOp.DEPOT
        assert tx.solde_apres == Decimal("25000")

    def test_deposit_is_dissociated_from_cotisation(self, active_member):
        """Le dépôt classique ne touche PAS le compte de cotisation (SavingsAccount)."""
        cotisation, _ = SavingsAccount.objects.get_or_create(
            member=active_member,
            defaults={"solde": Decimal("0"), "date_ouverture": timezone.localdate()},
        )
        cotisation.solde = Decimal("7000")
        cotisation.save(update_fields=["solde"])

        _confirm_classic_deposit(active_member, Decimal("5000"))

        cotisation.refresh_from_db()
        assert cotisation.solde == Decimal("7000")  # inchangé
        assert ClassicSavingsAccount.objects.get(member=active_member).solde == Decimal("5000")

    def test_two_deposits_accumulate(self, active_member):
        _confirm_classic_deposit(active_member, Decimal("10000"))
        _confirm_classic_deposit(active_member, Decimal("15000"))
        assert ClassicSavingsAccount.objects.get(member=active_member).solde == Decimal("25000")
        assert ClassicSavingsTransaction.objects.count() == 2


class TestMemberEndpoint:
    def test_classic_me_creates_account_lazily(self, client, active_member):
        client.force_login(active_member.user)
        resp = client.get(reverse("coop_savings:classic-me"))
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert body["solde"] in ("0.00", "0")
        assert "config" in body and body["config"]["libelle"] == "Épargne classique"
        assert ClassicSavingsAccount.objects.filter(member=active_member).exists()


class TestConfigEndpoint:
    def test_staff_can_read_and_update(self, client, admin_user):
        import json

        client.force_login(admin_user)
        url = reverse("coop_savings:classic-config")
        assert client.get(url).status_code == 200

        resp = client.patch(
            url,
            data=json.dumps({"taux_interet_mensuel": "0.0100", "depot_min": "1000"}),
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.content
        cfg = ClassicSavingsConfig.get_solo()
        assert cfg.taux_interet_mensuel == Decimal("0.0100")
        assert cfg.depot_min == Decimal("1000")

    def test_member_cannot_access_config(self, client, active_member):
        client.force_login(active_member.user)
        assert client.get(reverse("coop_savings:classic-config")).status_code == 403


class TestInitGuards:
    def test_deposit_blocked_when_product_inactive(self, client, active_member):
        import json

        cfg = ClassicSavingsConfig.get_solo()
        cfg.actif = False
        cfg.save(update_fields=["actif"])

        client.force_login(active_member.user)
        resp = client.post(
            reverse("coop_payments:init"),
            data=json.dumps(
                {
                    "type": "epargne_classique",
                    "montant": "5000",
                    "phone": "+237699000000",
                    "network": "MTN",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "classique" in resp.json()["detail"].lower()

    def test_deposit_blocked_below_minimum(self, client, active_member):
        import json

        cfg = ClassicSavingsConfig.get_solo()
        cfg.depot_min = Decimal("10000")
        cfg.save(update_fields=["depot_min"])

        client.force_login(active_member.user)
        resp = client.post(
            reverse("coop_payments:init"),
            data=json.dumps(
                {
                    "type": "epargne_classique",
                    "montant": "5000",
                    "phone": "+237699000000",
                    "network": "MTN",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert "minimum" in resp.json()["detail"].lower()
