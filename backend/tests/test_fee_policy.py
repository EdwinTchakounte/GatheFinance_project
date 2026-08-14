"""Tests ciblés de la politique de frais de transaction (fee_policy).

Couvre le cœur partagé par les 3 opérations (versement / retrait / transfert) :
  • calcul = montant × taux, arrondi au XAF (ROUND_HALF_UP) ;
  • périmètre admin (AppSetting) : une opération hors périmètre → 0 ;
  • taux nul par défaut → 0 ;
  • ne lève jamais (montant None → 0).

Le taux vit dans RateParam.TRANSACTION_FEE, le périmètre dans l'AppSetting
`payments.transaction_fee.operations` — tous deux réglables par l'admin.
"""
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.payments.fee_policy import (
    OP_RETRAIT,
    OP_TRANSFERT,
    OP_VERSEMENT,
    SETTING_KEY,
    fee_applies_to,
    transaction_fee_for,
)
from apps_coop.payments.models import RateParam

pytestmark = pytest.mark.django_db


def _set_rate(valeur: str):
    RateParam.objects.update_or_create(
        code=RateParam.Code.TRANSACTION_FEE,
        defaults={"libelle": "Frais tx", "valeur": Decimal(valeur), "actif": True},
    )


def _set_scope(csv: str):
    AppSetting.objects.update_or_create(cle=SETTING_KEY, defaults={"valeur": csv})


def test_no_rate_means_zero_on_all_operations():
    """Défaut (aucun RateParam TRANSACTION_FEE) → frais = 0 partout."""
    for op in (OP_VERSEMENT, OP_RETRAIT, OP_TRANSFERT):
        assert transaction_fee_for(Decimal("10000"), op) == Decimal("0")


@pytest.mark.parametrize("op", [OP_VERSEMENT, OP_RETRAIT, OP_TRANSFERT])
def test_fee_applied_when_rate_and_in_scope(op):
    """Taux 2 % + opération dans le périmètre → montant × 0.02."""
    _set_rate("0.02")
    _set_scope("versement,retrait,transfert")
    assert transaction_fee_for(Decimal("10000"), op) == Decimal("200")


def test_out_of_scope_operation_is_free():
    """Taux 2 % mais périmètre = {versement} → retrait et transfert = 0."""
    _set_rate("0.02")
    _set_scope("versement")
    assert transaction_fee_for(Decimal("10000"), OP_VERSEMENT) == Decimal("200")
    assert transaction_fee_for(Decimal("10000"), OP_RETRAIT) == Decimal("0")
    assert transaction_fee_for(Decimal("10000"), OP_TRANSFERT) == Decimal("0")
    assert fee_applies_to(OP_VERSEMENT) is True
    assert fee_applies_to(OP_RETRAIT) is False


def test_rounding_half_up_to_integer_xaf():
    """Arrondi au XAF entier, ROUND_HALF_UP : 1250 × 0.02 = 25 ; 1275 × 0.02 = 25.5 → 26."""
    _set_rate("0.02")
    _set_scope("versement,retrait,transfert")
    assert transaction_fee_for(Decimal("1250"), OP_VERSEMENT) == Decimal("25")
    assert transaction_fee_for(Decimal("1275"), OP_VERSEMENT) == Decimal("26")


def test_none_amount_never_raises():
    """montant None → 0 (ne lève jamais, sécurise les appels amont)."""
    _set_rate("0.02")
    _set_scope("versement,retrait,transfert")
    assert transaction_fee_for(None, OP_VERSEMENT) == Decimal("0")
