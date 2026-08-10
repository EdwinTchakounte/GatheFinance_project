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
    # 2026-08 (décision cliente) : deux déclarations Broad Range symétriques —
    # CGA (cga_adherent) et CFP (ancien_apprenant), toutes deux is_privilege.
    _activate_seed()
    assert privilege_declaration_field_ids("loan_request") == {
        "cga_adherent",
        "ancien_apprenant",
    }


def test_seed_declare_les_flags_preuve():
    # 2026-08 : deux preuves Broad Range flaggées is_brc_proof — CGA (cga_preuve)
    # et CFP (ancien_apprenant_preuve), alimentant la file BRC partagée.
    _activate_seed()
    assert brc_proof_field_ids("loan_request") == {
        "cga_preuve",
        "ancien_apprenant_preuve",
    }
