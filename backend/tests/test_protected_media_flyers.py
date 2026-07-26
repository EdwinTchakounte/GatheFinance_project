"""Le garde-fou `protected_media` (config/urls.py) doit exposer les flyers de
campagne au public tout en gardant privees les candidatures et pieces d'identite.

Regression 2026-07-26 : le prefixe public etait `coop/campaigns/` alors que le
champ `MicrocreditCampaign.flyer` uploade sous `coop/microcampaigns/flyers/`
-> flyers en 403 -> images cassees sur la vitrine.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


def _seed_file(media_root, rel_path):
    dest = Path(media_root) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"\xff\xd8\xff\xe0jpeg-bytes")  # entete JPEG minimale
    return rel_path


def test_flyer_is_public(tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        rel = _seed_file(tmp_path, "coop/microcampaigns/flyers/2026/07/flyer.jpeg")
        resp = Client().get(f"/media/{rel}")
    assert resp.status_code == 200, resp.content


def test_candidature_reste_privee_pour_anonyme(tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        # 403 renvoye avant meme la lecture du fichier -> pas besoin de le creer
        resp = Client().get(
            "/media/coop/microcampaigns/candidatures/2026/07/piece.pdf"
        )
    assert resp.status_code == 403


def test_cni_reste_privee_pour_anonyme(tmp_path):
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        resp = Client().get("/media/coop/avaliste/cni/2026/07/cni.jpg")
    assert resp.status_code == 403
