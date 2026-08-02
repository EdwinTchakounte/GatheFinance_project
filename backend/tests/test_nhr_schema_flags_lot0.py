"""LOT 0.4 — parité : le SEED loan_request porte les flags, le cœur les lit.

Prouve que le chemin schéma-driven (générique) couvre les champs NHR vivants,
donc que les constantes en dur pourront être retirées (0.5) sans perte de
comportement pour ces champs.
"""
from __future__ import annotations

import pytest

from apps_coop.forms.field_flags import (
    brc_proof_field_ids,
    privilege_declaration_field_ids,
)
from apps_coop.forms.management.commands.seed_form_schemas import (
    LOAN_REQUEST_SCHEMA,
)
from apps_coop.forms.models import FormSchema

pytestmark = pytest.mark.django_db


def _activate_seed():
    return FormSchema.objects.create(
        kind=FormSchema.Kind.LOAN_REQUEST,
        version=999,
        title="Demande de crédit (seed)",
        schema=LOAN_REQUEST_SCHEMA,
        is_active=True,
    )


def test_seed_declare_les_flags_privilege():
    # 2026-08 : section « CFP Broad Range » (ancien_apprenant) retirée du seed
    # (redondante avec l'attribut is_brc). Reste la déclaration CGA.
    _activate_seed()
    assert privilege_declaration_field_ids("loan_request") == {
        "cga_adherent",
    }


def test_seed_declare_les_flags_preuve():
    # 2026-08 : question CFP retirée du seed → seule la preuve CGA reste flaggée
    # dans le schéma. (L'attestation is_brc `brc_attestation` est reconnue au
    # niveau du handler d'upload, hors schéma — cf. test_brc_from_loan_attachment.)
    _activate_seed()
    assert brc_proof_field_ids("loan_request") == {
        "cga_preuve",
    }
