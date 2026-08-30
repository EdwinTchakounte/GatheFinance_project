"""Endpoint public de version mobile (gate de mise à jour forcée)."""
import pytest

pytestmark = pytest.mark.django_db


def test_app_version_public_defaults(client):
    resp = client.get("/api/v1/app-version/")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("min_version", "latest_version", "android_download_url", "update_message"):
        assert key in data
    assert data["min_version"]  # non vide (défaut réglementaire)


def test_app_version_reflects_appsetting(client):
    from apps_coop.audit.models import AppSetting

    AppSetting.objects.update_or_create(
        cle="mobile.min_version", defaults={"valeur": "1.1.0"}
    )
    resp = client.get("/api/v1/app-version/")
    assert resp.status_code == 200
    assert resp.json()["min_version"] == "1.1.0"
