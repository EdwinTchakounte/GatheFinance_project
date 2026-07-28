"""LOT 0 — parité finale (post-0.5) : les déclarations de privilège passent par le SCHÉMA.

Avant 0.5, une boucle compat en dur (loan_request views) forçait les flags NHR
dans extra_payload. Depuis 0.5, cette boucle et les constantes en dur ont été
retirées : les champs vivants (``ancien_apprenant``, ``cga_adherent``) sont des
champs DÉCLARÉS du FormSchema actif (attribut ``is_privilege_declaration``) et
``apply_form_schema`` les conserve nativement. Ce test prouve la parité via le
schéma — le cœur ne contient plus aucun nom de champ spécifique-coop.

Touchpoint 2 (preuve BRC → file /brc, attribut ``is_brc_proof``) : couvert par
``test_brc_from_loan_attachment.py`` (schéma actif) et ``test_nhr_schema_flags_lot0.py``.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.forms.management.commands.seed_form_schemas import LOAN_REQUEST_SCHEMA
from apps_coop.forms.models import FormSchema
from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _seed_fee():
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "Étude", "montant": Decimal("1000"), "actif": True},
    )


def _activate_loan_schema():
    return FormSchema.objects.create(
        kind=FormSchema.Kind.LOAN_REQUEST,
        version=999,
        title="Demande de crédit (seed)",
        schema=LOAN_REQUEST_SCHEMA,
        is_active=True,
    )


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _covered_member():
    m = MemberFactory()
    ClassicSavingsAccount.objects.update_or_create(
        member=m, defaults={"solde": Decimal("60000"), "date_ouverture": date.today()}
    )
    return m


def test_declarations_privilege_conservees_via_schema():
    """Avec le schéma actif flaggé, ancien_apprenant/cga_adherent atterrissent
    en extra_payload SANS aucune constante en dur (via apply_form_schema)."""
    _seed_fee()
    _activate_loan_schema()
    m = _covered_member()
    body = {
        "montant_demande": "50000",
        "duree_mois": 3,
        "motif": "Achat de marchandises pour ma boutique",
        # Les deux déclarations requises par le schéma (=non → pas de preuve exigée).
        "ancien_apprenant": "non",
        "cga_adherent": "non",
    }
    r = _api(m).post("/api/v1/loans/requests/", body, format="json")
    assert r.status_code == 201, r.content

    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert lr.extra_payload.get("ancien_apprenant") == "non"
    assert lr.extra_payload.get("cga_adherent") == "non"
