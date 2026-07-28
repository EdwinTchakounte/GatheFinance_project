"""G3 — criticité crédit : barème taux + montant (parts égales), settings-driven."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.loans.criticality_services import credit_criticality

pytestmark = pytest.mark.django_db


def _loan(montant, decouvert):
    return SimpleNamespace(
        montant=Decimal(montant), montant_decouvert=Decimal(decouvert)
    )


def test_faible_si_adosse():
    assert credit_criticality(_loan("100000", "0")) == "faible"


def test_moyen_petit_decouvert():
    # 20 % sur 100k → rate_norm 0.25, amount_norm 0.04, score ~0.145 → moyen.
    assert credit_criticality(_loan("100000", "20000")) == "moyen"


def test_eleve_gros_taux():
    # 80 % sur 100k → rate_norm 1, amount_norm 0.16, score ~0.58 → élevé.
    assert credit_criticality(_loan("100000", "80000")) == "eleve"


def test_critique_gros_taux_et_montant():
    # 400k découvert sur 500k → rate_norm 1, amount_norm 0.8, score 0.9 → critique.
    assert credit_criticality(_loan("500000", "400000")) == "critique"


def test_seuils_editables():
    # Abaisser le seuil critique à 0.5 → le cas 'élevé' (0.58) devient 'critique'.
    AppSetting.objects.update_or_create(
        cle="loans.criticality.score_critique", defaults={"valeur": "0.5"}
    )
    assert credit_criticality(_loan("100000", "80000")) == "critique"
