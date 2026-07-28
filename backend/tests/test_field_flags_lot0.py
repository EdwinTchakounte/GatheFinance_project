"""LOT 0.2 — le mécanisme générique : un champ se déclare son rôle via le schéma.

Prouve que le cœur peut reconnaître « preuve de privilège » / « déclaration de
privilège » à partir des attributs JSON du FormSchema actif, SANS aucune constante
spécifique à une coopérative. C'est ce qui rendra le cœur réutilisable (GATHE/NHR).
"""
from __future__ import annotations

import pytest

from apps_coop.forms.field_flags import (
    brc_proof_field_ids,
    privilege_declaration_field_ids,
)
from apps_coop.forms.models import FormSchema

pytestmark = pytest.mark.django_db


def _active_loan_schema(fields):
    return FormSchema.objects.create(
        kind=FormSchema.Kind.LOAN_REQUEST,
        version=1,
        title="Demande de crédit",
        schema={"sections": [{"id": "s1", "title": "S1", "fields": fields}]},
        is_active=True,
    )


def test_flags_lus_depuis_le_schema_actif():
    _active_loan_schema(
        [
            {"id": "montant_demande", "type": "number"},  # aucun flag
            {"id": "preuve_x", "type": "file", "is_brc_proof": True},
            {"id": "declare_y", "type": "radio", "is_privilege_declaration": True},
        ]
    )
    assert brc_proof_field_ids("loan_request") == {"preuve_x"}
    assert privilege_declaration_field_ids("loan_request") == {"declare_y"}


def test_pas_de_schema_actif_renvoie_vide():
    assert brc_proof_field_ids("loan_request") == set()
    assert privilege_declaration_field_ids("loan_request") == set()


def test_noms_generiques_pas_de_dependance_nhr():
    # Des noms de champs quelconques (pas cga/cfp) sont reconnus : le mécanisme
    # ne dépend d'aucun nom spécifique-client.
    _active_loan_schema(
        [{"id": "attestation_centre", "type": "file", "is_brc_proof": True}]
    )
    assert "attestation_centre" in brc_proof_field_ids("loan_request")
