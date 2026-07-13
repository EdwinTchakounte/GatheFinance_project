"""Fenêtre du placement épargne classique — fermeture datée (1er août 2026).

Après la date-limite, tout NOUVEAU versement d'épargne classique va en LIBRE et
l'ajout d'une tranche de placement est refusé. Les placements existants ne sont
pas touchés (testé implicitement : on ne bascule aucune donnée).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.placement import placement_open, placement_open_for_member

pytestmark = pytest.mark.django_db


def _set(key: str, val: str) -> None:
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": val})


def _set_adhesion(member, months_ago):
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago + 5)
    member.save(update_fields=["date_adhesion"])
    return member


class TestPlacementWindow:
    def test_open_before_cutoff(self):
        assert placement_open(on=date(2026, 7, 31)) is True

    def test_closed_from_cutoff(self):
        assert placement_open(on=date(2026, 8, 1)) is False
        assert placement_open(on=date(2026, 12, 1)) is False

    def test_global_toggle_off_closes(self):
        _set("epargne.placement.enabled", "false")
        assert placement_open(on=date(2026, 7, 1)) is False

    def test_deadline_tunable(self):
        _set("savings.placement.closed_from", "2026-09-01")
        assert placement_open(on=date(2026, 8, 15)) is True
        assert placement_open(on=date(2026, 9, 1)) is False

    def test_add_tranche_blocked_after_cutoff(self, active_member):
        _set("savings.placement.closed_from", "2020-01-01")  # date déjà passée
        _set("lender.tranche.min_amount", "1000")
        opt_in_lender(member=active_member, is_global=False)
        with pytest.raises(ValueError, match="placement est fermé"):
            add_tranche(member=active_member, montant=Decimal("10000"))

    def test_add_tranche_ok_before_cutoff(self, active_member):
        _set("savings.placement.closed_from", "2099-01-01")  # loin dans le futur
        _set("lender.tranche.min_amount", "1000")
        opt_in_lender(member=active_member, is_global=False)
        t = add_tranche(member=active_member, montant=Decimal("10000"))
        assert t.montant == Decimal("10000")


class TestPlacementMemberWindow:
    """Fenêtre PAR MEMBRE : placement ouvert seulement les N premiers mois."""

    def test_fresh_member_can_place(self, active_member):
        _set("savings.placement.closed_from", "2099-01-01")  # global ouvert
        _set_adhesion(active_member, months_ago=1)
        assert placement_open_for_member(active_member) is True

    def test_member_past_window_cannot_place(self, active_member):
        _set("savings.placement.closed_from", "2099-01-01")
        _set_adhesion(active_member, months_ago=8)  # > 6 mois
        assert placement_open_for_member(active_member) is False

    def test_window_tunable(self, active_member):
        _set("savings.placement.closed_from", "2099-01-01")
        _set("epargne.placement.eligibility_months", "12")
        _set_adhesion(active_member, months_ago=8)  # < 12 mois
        assert placement_open_for_member(active_member) is True

    def test_window_zero_disables_member_gate(self, active_member):
        _set("savings.placement.closed_from", "2099-01-01")
        _set("epargne.placement.eligibility_months", "0")
        _set_adhesion(active_member, months_ago=24)  # très ancien
        assert placement_open_for_member(active_member) is True

    def test_global_cutoff_still_wins(self, active_member):
        _set("savings.placement.closed_from", "2020-01-01")  # déjà fermé
        _set_adhesion(active_member, months_ago=1)  # membre frais
        assert placement_open_for_member(active_member) is False

    def test_init_payment_rejects_placement_out_of_window(self, active_member):
        """POST /payments/init/ refuse un placement pour un membre hors fenêtre."""
        _set("savings.placement.closed_from", "2099-01-01")
        _set_adhesion(active_member, months_ago=8)
        client = APIClient()
        client.force_authenticate(user=active_member.user)
        r = client.post(
            "/api/v1/payments/init/",
            {"type": "epargne_classique", "montant": "5000",
             "phone": "237699000000", "is_placement": True},
            format="json",
        )
        assert r.status_code == 400, r.content
        assert "placement" in r.json()["detail"].lower()

    def test_init_payment_allows_libre_out_of_window(self, active_member):
        """Même membre hors fenêtre : un dépôt LIBRE reste accepté."""
        _set("savings.placement.closed_from", "2099-01-01")
        _set_adhesion(active_member, months_ago=8)
        client = APIClient()
        client.force_authenticate(user=active_member.user)
        r = client.post(
            "/api/v1/payments/init/",
            {"type": "epargne_classique", "montant": "5000",
             "phone": "237699000000", "is_placement": False},
            format="json",
        )
        assert r.status_code in (200, 201), r.content
