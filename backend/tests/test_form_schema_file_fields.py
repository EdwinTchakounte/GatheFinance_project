"""Régression — champs FICHIER dans un FormSchema (preuves BRC CGA/CFP).

Bug trouvé en simulation locale 2026-08-10 : les preuves CGA/CFP sont des champs
``type=file`` du schéma, uploadés HORS-BANDE (endpoint attachments) APRÈS la
création. Or apply_form_schema :
  (1) exigeait le fichier dès la création (visible+required quand la réponse est
      « oui ») → ValidationError → bascule legacy → extra_payload vidé → la
      déclaration « cga_adherent=oui » était SILENCIEUSEMENT PERDUE ;
  (2) mettait un fichier passé inline dans extra_payload (non-JSON) → 500.

Correctif : les champs ``type=file`` sont exclus de la validation ``required``
ET du split extra_payload.
"""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers

from apps_coop.forms.models import FormSchema
from apps_coop.forms.services import apply_form_schema

pytestmark = pytest.mark.django_db

_SCHEMA = {
    "sections": [
        {
            "id": "profil",
            "fields": [
                {
                    "id": "cga_adherent", "type": "radio", "required": True,
                    "is_privilege_declaration": True,
                    "options": [{"value": "oui"}, {"value": "non"}],
                },
                {
                    "id": "cga_preuve", "type": "file", "required": True,
                    "is_brc_proof": True,
                    "condition": {"field": "cga_adherent", "operator": "equals", "value": "oui"},
                },
            ],
        }
    ]
}


def _activate():
    FormSchema.objects.filter(kind=FormSchema.Kind.LOAN_REQUEST).update(is_active=False)
    return FormSchema.objects.create(
        kind=FormSchema.Kind.LOAN_REQUEST, version=999, schema=_SCHEMA, is_active=True
    )


def test_oui_sans_fichier_capture_la_declaration():
    """cga=oui + fichier absent (uploadé séparément) → PAS d'erreur, « oui » capturé."""
    _activate()
    _, extra, _ = apply_form_schema("loan_request", {"cga_adherent": "oui"}, hardcoded_keys=set())
    assert extra == {"cga_adherent": "oui"}


def test_fichier_inline_exclu_de_extra_payload():
    """Un fichier passé inline ne doit jamais atterrir dans extra_payload (pas de 500)."""
    _activate()
    f = SimpleUploadedFile("preuve.pdf", b"%PDF", content_type="application/pdf")
    _, extra, _ = apply_form_schema(
        "loan_request", {"cga_adherent": "oui", "cga_preuve": f}, hardcoded_keys=set()
    )
    assert "cga_preuve" not in extra
    assert extra == {"cga_adherent": "oui"}


def test_required_non_fichier_toujours_applique():
    """Le required reste appliqué pour les champs NON-fichier (radio manquant)."""
    _activate()
    with pytest.raises(serializers.ValidationError):
        apply_form_schema("loan_request", {}, hardcoded_keys=set())


def test_non_visible_file_ok():
    """cga=non → preuve non visible, non requise, absente : OK, « non » capturé."""
    _activate()
    _, extra, _ = apply_form_schema("loan_request", {"cga_adherent": "non"}, hardcoded_keys=set())
    assert extra == {"cga_adherent": "non"}
