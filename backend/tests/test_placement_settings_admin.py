"""Réglages du placement administrables depuis le dashboard — 2026-10.

Les trois verrous du placement existaient en AppSetting mais ne figuraient pas
au catalogue des tunables : `admin_settings_update` répondait « Clé inconnue ou
non tunable » et seul un shell Django sur le serveur pouvait les changer. Or la
date de fermeture et la fenêtre d'ancienneté sont des décisions de gestion qui
bougent.

Un piège propre à la date : `placement.py` rattrape un `ValueError` et retombe
sur le défaut. Une date mal saisie ne lèverait donc aucune erreur — l'admin
croirait avoir repoussé la fermeture alors que rien n'aurait changé. D'où la
validation stricte du format, testée ici.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.audit.tunables import get_entry
from apps_coop.savings.placement import (
    PLACEMENT_CLOSED_FROM_DEFAULT,
    PLACEMENT_ELIGIBILITY_MONTHS_DEFAULT,
    placement_eligibility_months,
    placement_open,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

CLES = (
    "epargne.placement.enabled",
    "savings.placement.closed_from",
    "epargne.placement.eligibility_months",
)


def _url(cle: str) -> str:
    return f"/api/v1/audit/admin/settings/{cle}/"


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class TestCatalogue:
    @pytest.mark.parametrize("cle", CLES)
    def test_la_cle_est_au_catalogue(self, cle):
        assert get_entry(cle) is not None

    def test_elles_apparaissent_dans_le_dashboard(self):
        body = _api(_staff()).get("/api/v1/audit/admin/settings/").json()

        assert set(CLES) <= {r["key"] for r in body["settings"]}
        assert "placement" in {g["key"] for g in body["groups"]}

    def test_les_defauts_du_catalogue_suivent_le_code(self):
        """Le catalogue reprend `savings/placement.py` au lieu de recopier les
        valeurs : sans cela les deux divergeraient à la première évolution."""
        assert get_entry("savings.placement.closed_from")["default"] == (
            PLACEMENT_CLOSED_FROM_DEFAULT
        )
        assert get_entry("epargne.placement.eligibility_months")["default"] == str(
            PLACEMENT_ELIGIBILITY_MONTHS_DEFAULT
        )


class TestEdition:
    def test_repousser_la_fermeture_rouvre_le_placement(self):
        """Le réglage doit AGIR, pas seulement être stocké."""
        from datetime import date

        res = _api(_staff()).patch(
            _url("savings.placement.closed_from"),
            {"value": "2099-01-01"},
            format="json",
        )

        assert res.status_code == 200, res.content
        assert placement_open(date(2026, 10, 6)) is True

    def test_changer_la_fenetre_est_pris_en_compte(self):
        res = _api(_staff()).patch(
            _url("epargne.placement.eligibility_months"),
            {"value": "12"},
            format="json",
        )

        assert res.status_code == 200, res.content
        assert placement_eligibility_months() == 12

    def test_l_interrupteur_ferme_tout(self):
        res = _api(_staff()).patch(
            _url("epargne.placement.enabled"), {"value": "false"}, format="json",
        )

        assert res.status_code == 200, res.content
        assert placement_open() is False


class TestFormatDate:
    @pytest.mark.parametrize(
        "mauvais", ["01/08/2026", "2026-13-01", "bientot", "", "2026-08"]
    )
    def test_une_date_mal_formee_est_refusee(self, mauvais):
        """Sans ce refus, la valeur partirait en base et `placement.py`
        retomberait silencieusement sur le défaut."""
        res = _api(_staff()).patch(
            _url("savings.placement.closed_from"), {"value": mauvais}, format="json",
        )

        assert res.status_code == 400
        assert not AppSetting.objects.filter(cle="savings.placement.closed_from").exists()

    def test_une_date_valide_passe(self):
        res = _api(_staff()).patch(
            _url("savings.placement.closed_from"),
            {"value": "2027-03-15"},
            format="json",
        )

        assert res.status_code == 200
        assert (
            AppSetting.objects.get(cle="savings.placement.closed_from").valeur
            == "2027-03-15"
        )

    def test_une_fenetre_negative_est_refusee(self):
        res = _api(_staff()).patch(
            _url("epargne.placement.eligibility_months"), {"value": "-3"}, format="json",
        )

        assert res.status_code == 400


def test_un_membre_simple_ne_peut_pas_editer():
    membre = MemberFactory()

    res = _api(membre.user).patch(
        _url("savings.placement.closed_from"), {"value": "2099-01-01"}, format="json",
    )

    assert res.status_code in (401, 403)
