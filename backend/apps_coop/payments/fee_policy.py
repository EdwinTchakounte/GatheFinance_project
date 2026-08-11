"""Politique d'application du frais de transaction (%) par opération.

Deux réglages ADMIN, sans redéploiement :
  • le TAUX vit dans ``RateParam.TRANSACTION_FEE`` (0 par défaut) ;
  • le PÉRIMÈTRE (quelles opérations sont frappées) vit dans l'AppSetting
    ``payments.transaction_fee.operations`` (liste CSV parmi
    ``versement``, ``retrait``, ``transfert``).

Le frais est prélevé **EN PLUS, sur le solde** (décision client 2026-08-11) :
le membre supporte ``montant + frais`` et le bénéficiaire reçoit le montant
plein (le versement crédite ``montant``, le retrait paie ``montant``, le
transfert rembourse ``montant``). La coopérative encaisse ``frais``.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps_coop.audit.services import get_str_setting

from .models import RateParam
from .rates import get_rate

OP_VERSEMENT = "versement"
OP_RETRAIT = "retrait"
OP_TRANSFERT = "transfert"
ALL_OPERATIONS = (OP_VERSEMENT, OP_RETRAIT, OP_TRANSFERT)

SETTING_KEY = "payments.transaction_fee.operations"
# Défaut : les 3 opérations sont dans le périmètre (le frais reste nul tant que
# le taux TRANSACTION_FEE n'est pas relevé > 0).
DEFAULT_OPERATIONS = "versement,retrait,transfert"


def fee_operations() -> set[str]:
    """Ensemble des opérations dans le périmètre du frais (admin-modifiable)."""
    raw = get_str_setting(SETTING_KEY, DEFAULT_OPERATIONS)
    return {o.strip().lower() for o in str(raw).split(",")} & set(ALL_OPERATIONS)


def fee_applies_to(operation: str) -> bool:
    return operation in fee_operations()


def transaction_fee_for(montant, operation: str) -> Decimal:
    """Frais (arrondi au XAF entier) dû sur ``montant`` pour ``operation``.

    Renvoie ``Decimal('0')`` si l'opération est hors périmètre OU si le taux
    est nul. Ne lève jamais.
    """
    if montant is None or not fee_applies_to(operation):
        return Decimal("0")
    rate = get_rate(RateParam.Code.TRANSACTION_FEE)
    if rate is None or rate <= 0:
        return Decimal("0")
    return (Decimal(montant) * Decimal(rate)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
