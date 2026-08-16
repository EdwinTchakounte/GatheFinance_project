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
# Défaut : SEUL le versement est dans le périmètre (retrait et transfert → 0).
# Le frais versement s'applique donc automatiquement (taux TRANSACTION_FEE,
# 3 % par défaut) ; l'admin peut élargir le périmètre sur la page Coûts.
DEFAULT_OPERATIONS = "versement"


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
    return _apply_rate(montant)


# ── Frais sur les PAIEMENTS ENTRANTS (payin Mobile Money) ─────────────────────
# Le frais versement ne se limite plus à l'épargne : il s'applique à une LISTE de
# types de paiement entrants, entièrement pilotée par l'admin (aucun hardcode).

PAYIN_TYPES_SETTING_KEY = "payments.transaction_fee.payin_types"

# Tous les types de paiement ENTRANT candidats (le membre paie via Mobile Money).
ALL_PAYIN_TYPES = (
    "epargne",
    "epargne_classique",
    "caisse_scolaire",
    "tontine_alimentaire",
    "frais_inscription",
    "frais_adhesion",
    "frais_carnet",
    "frais_demande_credit",
    "frais_reconduction",
    "remboursement",
)
# Défaut : tout ce que le membre PAIE en entrée, SAUF le remboursement de crédit
# (l'admin peut l'ajouter/retirer sur la page Coûts).
DEFAULT_PAYIN_TYPES = ",".join(t for t in ALL_PAYIN_TYPES if t != "remboursement")


def payin_fee_types() -> set[str]:
    """Types de paiement entrant frappés par le frais (admin-modifiable)."""
    raw = get_str_setting(PAYIN_TYPES_SETTING_KEY, DEFAULT_PAYIN_TYPES)
    return {t.strip().lower() for t in str(raw).split(",")} & set(ALL_PAYIN_TYPES)


def fee_applies_to_payin(payment_type: str) -> bool:
    """Le frais s'applique-t-il à ce paiement entrant ?

    Deux niveaux, tous deux admin : l'opération ``versement`` doit être active
    (interrupteur maître) ET le type doit figurer dans la liste configurée.
    """
    return OP_VERSEMENT in fee_operations() and payment_type in payin_fee_types()


def transaction_fee_for_payin(montant, payment_type: str) -> Decimal:
    """Frais (arrondi XAF) sur un paiement ENTRANT de type ``payment_type``.

    Renvoie 0 si le type est hors périmètre configuré OU si le taux est nul.
    Le membre paie ``montant + frais`` (Tara facture le total).
    """
    if montant is None or not fee_applies_to_payin(payment_type):
        return Decimal("0")
    return _apply_rate(montant)


def _apply_rate(montant) -> Decimal:
    rate = get_rate(RateParam.Code.TRANSACTION_FEE)
    if rate is None or rate <= 0:
        return Decimal("0")
    return (Decimal(montant) * Decimal(rate)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
