"""Rôle déclaratif d'un champ, lu depuis le FormSchema actif (modularisation Lot 0).

Le cœur ne doit pas connaître les NOMS de champs spécifiques à une coopérative
(``cga_brc_preuve``, ``ancien_apprenant``…). À la place, un champ **se déclare
lui-même** via des clés JSON dans le schéma :

  - ``is_brc_proof: true``            → ce champ (type file) porte une preuve de
    privilège → sa pièce alimente la file de validation BRC du back-office.
  - ``is_privilege_declaration: true`` → ce champ est un flag déclaratif de
    privilège → sa valeur est conservée en ``extra_payload``.

Ainsi le même cœur sert GATHE, NHR, etc. : seul le schéma (données) change.
"""
from __future__ import annotations

from .models import FormSchema
from .services import _iter_fields


def _flagged_field_ids(kind: str, flag: str) -> set[str]:
    row = FormSchema.objects.filter(kind=kind, is_active=True).first()
    if row is None:
        return set()
    return {f["id"] for f in _iter_fields(row.schema or {}) if f.get(flag)}


# Attestation liée à l'attribut hardcodé ``LoanRequest.is_brc`` (« a fréquenté
# le centre de formation BRC »). Ce n'est PAS un champ du FormSchema (toggle
# codé en dur côté client) : le handler d'upload la reconnaît explicitement
# comme preuve BRC, en plus des champs flaggés ``is_brc_proof`` dans le schéma.
# On la garde HORS de ``brc_proof_field_ids`` pour préserver la pureté du
# mécanisme générique schema-driven (réutilisable GATHE/NHR).
BRC_ATTESTATION_FIELD_ID = "brc_attestation"


def brc_proof_field_ids(kind: str = "loan_request") -> set[str]:
    """Champs marqués preuve de privilège (→ file BRC) dans le schéma actif."""
    return _flagged_field_ids(kind, "is_brc_proof")


def privilege_declaration_field_ids(kind: str = "loan_request") -> set[str]:
    """Champs marqués déclaration de privilège (→ conservés) dans le schéma actif."""
    return _flagged_field_ids(kind, "is_privilege_declaration")


def field_labels(kind: str = "loan_request") -> dict[str, str]:
    """``{id: label}`` des champs du schéma actif — libellé d'affichage générique
    (ex. pour la file BRC), sans dictionnaire de noms spécifiques-coop en dur."""
    row = FormSchema.objects.filter(kind=kind, is_active=True).first()
    if row is None:
        return {}
    return {f["id"]: f.get("label", f["id"]) for f in _iter_fields(row.schema or {})}
