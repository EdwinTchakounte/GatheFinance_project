"""Fenêtre du placement épargne classique — fermeture datée (1er août 2026).

Après la date-limite, tout NOUVEAU versement d'épargne classique va en LIBRE et
l'ajout d'une tranche de placement est refusé. Les placements existants ne sont
pas touchés (testé implicitement : on ne bascule aucune donnée).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.placement import placement_open

pytestmark = pytest.mark.django_db


def _set(key: str, val: str) -> None:
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": val})


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
