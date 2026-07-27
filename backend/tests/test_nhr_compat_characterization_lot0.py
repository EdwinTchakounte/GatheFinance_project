"""LOT 0 — Filet de caractérisation du comportement NHR AVANT modularisation.

But : figer le comportement ACTUEL (spécifique NHR câblé dans le cœur) pour prouver
la PARITÉ après extraction vers FormSchema/attributs (lots 0.2→0.5). On ne modifie
rien ici — on capture.

Touchpoint 1 (ce fichier) : la « boucle compat démo NHR » de ``loan_request_create``
(``views.py`` ~373-380) conserve les flags déclaratifs NHR (ancien_apprenant,
cga_adherent, cga_brc_member, cfp_brc_apprenant) dans ``LoanRequest.extra_payload``
MÊME quand le FormSchema actif ne les déclare pas.

Touchpoint 2 (preuve BRC → file /brc à l'upload) : déjà couvert par
``test_brc_from_loan_attachment.py`` — pas redoublé ici.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

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


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _covered_member():
    """Membre auto-couvert (épargne classique ≥ montant) → voie senior_brc valide,
    garde-fou apport + éligibilité passés → la demande est créée."""
    m = MemberFactory()
    ClassicSavingsAccount.objects.update_or_create(
        member=m, defaults={"solde": Decimal("60000"), "date_ouverture": date.today()}
    )
    return m


NHR_FLAGS = {
    "ancien_apprenant": "oui",
    "cga_adherent": "non",
    "cga_brc_member": "oui",
    "cfp_brc_apprenant": "non",
}


def test_flags_nhr_conserves_dans_extra_payload_hors_schema():
    """Les 4 flags NHR arrivent en extra_payload même absents du FormSchema actif."""
    _seed_fee()
    m = _covered_member()
    body = {
        "montant_demande": "50000",
        "duree_mois": 3,
        "motif": "Achat de marchandises pour ma boutique",
        **NHR_FLAGS,
    }
    r = _api(m).post("/api/v1/loans/requests/", body, format="json")
    assert r.status_code == 201, r.content

    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    for key, val in NHR_FLAGS.items():
        assert lr.extra_payload.get(key) == val, (
            f"{key} attendu={val!r} obtenu={lr.extra_payload.get(key)!r}"
        )


def test_valeurs_hors_oui_non_ignorees():
    """La boucle compat ne conserve QUE 'oui'/'non' (garde-fou anti-bruit)."""
    _seed_fee()
    m = _covered_member()
    body = {
        "montant_demande": "50000",
        "duree_mois": 3,
        "motif": "Achat de marchandises pour ma boutique",
        "cga_adherent": "peut-etre",  # hors oui/non → ignoré
    }
    r = _api(m).post("/api/v1/loans/requests/", body, format="json")
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    assert "cga_adherent" not in lr.extra_payload
