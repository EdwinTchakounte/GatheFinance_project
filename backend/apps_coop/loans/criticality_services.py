"""Gouvernance G3 — criticité d'un crédit (indicateur d'aide à la décision).

Avis SOUPLE pour le comité (jamais un couperet) : il agrège, à parts égales, le
**taux de découvert** (part non adossée / montant, calibré sur le plafond
structurel 80 %) et le **montant absolu** à découvert (normalisé par un montant
de référence). Tous les curseurs sont des AppSettings (règlement, éditables).

Niveaux : ``faible`` (adossé) · ``moyen`` · ``eleve`` · ``critique``.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from apps_coop.audit.services import get_str_setting

FAIBLE = "faible"
MOYEN = "moyen"
ELEVE = "eleve"
CRITIQUE = "critique"

LABELS = {
    FAIBLE: "Faible",
    MOYEN: "Moyen",
    ELEVE: "Élevé",
    CRITIQUE: "Critique",
}

# Plafond structurel du découvert (apport 20 % obligatoire) — sert à calibrer le
# score de taux : 80 % de découvert = taux maximal possible.
_DECOUVERT_MAX_RATE = Decimal("0.80")


def _dec_setting(key: str, default: Decimal) -> Decimal:
    raw = get_str_setting(key, str(default))
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def credit_criticality(loan) -> str:
    """Niveau de criticité (clé) d'un ``Loan`` à partir de son découvert tracé."""
    montant = Decimal(getattr(loan, "montant", 0) or 0)
    decouvert = Decimal(getattr(loan, "montant_decouvert", 0) or 0)
    if montant <= 0 or decouvert <= 0:
        return FAIBLE  # crédit adossé (aucune exposition sur confiance)

    amount_ref = _dec_setting("loans.criticality.amount_ref", Decimal("500000"))
    s_eleve = _dec_setting("loans.criticality.score_eleve", Decimal("0.5"))
    s_critique = _dec_setting("loans.criticality.score_critique", Decimal("0.75"))

    rate_norm = min(Decimal("1"), (decouvert / montant) / _DECOUVERT_MAX_RATE)
    amount_norm = (
        min(Decimal("1"), decouvert / amount_ref)
        if amount_ref > 0
        else Decimal("0")
    )
    # Parts égales entre taux et montant absolu.
    score = (rate_norm + amount_norm) / 2

    if score >= s_critique:
        return CRITIQUE
    if score >= s_eleve:
        return ELEVE
    return MOYEN


def credit_criticality_label(loan) -> str:
    return LABELS.get(credit_criticality(loan), LABELS[FAIBLE])
