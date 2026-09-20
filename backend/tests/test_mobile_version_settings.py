"""Administration des versions de l'application mobile.

Contexte : la porte de mise à jour (``GET /api/v1/app-version/``) est publique
et lue par l'app AVANT toute connexion. Ses valeurs étaient censées être
pilotables depuis le dashboard, mais les clés ``mobile.*`` ne figuraient pas
au catalogue des tunables : le PATCH répondait « Clé inconnue » et il fallait
passer par l'admin Django. Ces tests figent la correction.

Ce qu'ils garantissent :
  - les quatre clés sont éditables depuis le dashboard ;
  - un numéro de version mal formé est refusé, parce que le comparateur côté
    mobile transforme tout composant illisible en 0 (« 1.2 » passerait
    silencieusement, « 12.0.0 » bloquerait tout le monde) ;
  - on ne peut pas exiger une version plus récente que la dernière publiée —
    ce serait un blocage sans issue depuis le téléphone ;
  - l'endpoint public et le catalogue ne peuvent plus diverger.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.audit.tunables import get_entry
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

VERSION_URL = "/api/v1/app-version/"
CLES = (
    "mobile.min_version",
    "mobile.latest_version",
    "mobile.android_download_url",
    "mobile.update_message",
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
    c.force_authenticate(user=user)
    return c


# --- Les clés sont administrables ------------------------------------------


class TestCatalogue:
    def test_les_quatre_cles_sont_au_catalogue(self):
        for cle in CLES:
            assert get_entry(cle) is not None, f"{cle} absente du catalogue"

    def test_elles_apparaissent_dans_la_liste_du_dashboard(self):
        body = _api(_staff()).get("/api/v1/audit/admin/settings/").json()

        presentes = {r["key"] for r in body["settings"]}
        assert set(CLES) <= presentes

        groupes = {g["key"] for g in body["groups"]}
        assert "mobile" in groupes

    def test_le_groupe_mobile_est_affiche_en_premier(self):
        """C'est le réglage touché à chaque publication Play Store, à la
        différence des paramètres réglementaires qui ne bougent presque
        jamais."""
        body = _api(_staff()).get("/api/v1/audit/admin/settings/").json()
        assert body["groups"][0]["key"] == "mobile"

    @pytest.mark.parametrize("cle", CLES)
    def test_chaque_cle_est_editable_depuis_le_dashboard(self, cle):
        valeurs = {
            "mobile.min_version": "1.2.0",
            "mobile.latest_version": "1.2.0",
            "mobile.android_download_url": "https://play.google.com/store/apps/details?id=x",
            "mobile.update_message": "Nouvelle version disponible.",
        }
        # L'ordre compte pour min_version : la dernière publiée d'abord.
        if cle == "mobile.min_version":
            AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")

        res = _api(_staff()).patch(_url(cle), {"value": valeurs[cle]}, format="json")

        assert res.status_code == 200, res.content
        assert AppSetting.objects.get(cle=cle).valeur == valeurs[cle]


# --- Format des versions ----------------------------------------------------


class TestFormatVersion:
    @pytest.mark.parametrize("mauvais", ["1.2", "v1.2.0", "1.2.0.1", "", "abc", "1.2.x"])
    def test_refuse_un_numero_mal_forme(self, mauvais):
        res = _api(_staff()).patch(
            _url("mobile.latest_version"), {"value": mauvais}, format="json"
        )

        assert res.status_code == 400
        assert not AppSetting.objects.filter(cle="mobile.latest_version").exists()

    def test_refuse_un_nombre_absurde(self):
        """« 12345.0.0 » n'est pas une version : c'est une faute de frappe qui
        bloquerait tout le monde si elle atterrissait dans min_version."""
        res = _api(_staff()).patch(
            _url("mobile.latest_version"), {"value": "12345.0.0"}, format="json"
        )

        assert res.status_code == 400

    def test_accepte_un_numero_valide(self):
        res = _api(_staff()).patch(
            _url("mobile.latest_version"), {"value": "1.2.0"}, format="json"
        )

        assert res.status_code == 200

    @pytest.mark.parametrize(
        "mauvaise_url", ["http://exemple.fr", "play.google.com", "https://a b.fr", ""]
    )
    def test_refuse_une_url_non_https(self, mauvaise_url):
        res = _api(_staff()).patch(
            _url("mobile.android_download_url"), {"value": mauvaise_url}, format="json"
        )

        assert res.status_code == 400


# --- Le garde-fou : pas de blocage sans issue -------------------------------


class TestPorteFranchissable:
    def test_refuse_un_minimum_superieur_a_la_derniere_publiee(self):
        """Sinon : écran de blocage pour tous, invitation à mettre à jour, et
        aucune version à installer. Irrattrapable depuis le téléphone."""
        AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")

        res = _api(_staff()).patch(
            _url("mobile.min_version"), {"value": "1.3.0"}, format="json"
        )

        assert res.status_code == 400
        assert "bloques" in res.json()["detail"].lower() or "bloqués" in res.json()["detail"].lower()
        assert not AppSetting.objects.filter(cle="mobile.min_version").exists()

    def test_refuse_aussi_dans_l_autre_sens(self):
        """Abaisser la dernière publiée sous le minimum exigé produit le même
        cul-de-sac."""
        AppSetting.objects.create(cle="mobile.min_version", valeur="1.2.0")
        AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")

        res = _api(_staff()).patch(
            _url("mobile.latest_version"), {"value": "1.1.0"}, format="json"
        )

        assert res.status_code == 400
        assert AppSetting.objects.get(cle="mobile.latest_version").valeur == "1.2.0"

    def test_accepte_un_minimum_egal_a_la_derniere(self):
        """Mise à jour forcée vers la version publiée : cas légitime."""
        AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")

        res = _api(_staff()).patch(
            _url("mobile.min_version"), {"value": "1.2.0"}, format="json"
        )

        assert res.status_code == 200

    def test_accepte_un_minimum_inferieur(self):
        AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")

        res = _api(_staff()).patch(
            _url("mobile.min_version"), {"value": "1.0.0"}, format="json"
        )

        assert res.status_code == 200

    def test_la_sequence_sure_est_possible_de_bout_en_bout(self):
        """Publier, annoncer, puis forcer — l'ordre que le garde-fou impose."""
        api = _api(_staff())

        assert api.patch(
            _url("mobile.latest_version"), {"value": "1.2.0"}, format="json"
        ).status_code == 200
        assert api.patch(
            _url("mobile.min_version"), {"value": "1.2.0"}, format="json"
        ).status_code == 200

        body = APIClient().get(VERSION_URL).json()
        assert body["latest_version"] == "1.2.0"
        assert body["min_version"] == "1.2.0"


# --- L'endpoint public et le catalogue ne divergent plus --------------------


class TestEndpointPublic:
    def test_sans_reglage_en_base_l_endpoint_sert_les_defauts_du_catalogue(self):
        """Ces défauts vivaient en double, en dur dans la vue : les deux
        avaient divergé."""
        assert not AppSetting.objects.filter(cle__startswith="mobile.").exists()

        body = APIClient().get(VERSION_URL).json()

        assert body["min_version"] == get_entry("mobile.min_version")["default"]
        assert body["latest_version"] == get_entry("mobile.latest_version")["default"]
        assert body["android_download_url"] == get_entry("mobile.android_download_url")["default"]
        assert body["update_message"] == get_entry("mobile.update_message")["default"]

    def test_un_reglage_en_base_prend_le_dessus(self):
        AppSetting.objects.create(cle="mobile.latest_version", valeur="1.2.0")
        AppSetting.objects.create(
            cle="mobile.android_download_url",
            valeur="https://play.google.com/store/apps/details?id=com.gathefinance.gathe_finance",
        )

        body = APIClient().get(VERSION_URL).json()

        assert body["latest_version"] == "1.2.0"
        assert "play.google.com" in body["android_download_url"]

    def test_reste_public(self):
        """L'app doit pouvoir interroger la porte avant toute connexion."""
        assert APIClient().get(VERSION_URL).status_code == 200


# --- Accès ------------------------------------------------------------------


def test_un_membre_simple_ne_peut_pas_editer():
    membre = MemberFactory()

    res = _api(membre.user).patch(
        _url("mobile.min_version"), {"value": "9.9.9"}, format="json"
    )

    assert res.status_code in (401, 403)
    assert not AppSetting.objects.filter(cle="mobile.min_version").exists()
