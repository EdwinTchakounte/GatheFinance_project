"""États par carnet — agrégation des écritures d'un membre, groupées par carnet.

Maintenant que CHAQUE écriture porte son carnet (``booklet_order``), on peut
présenter, pour chaque carnet du membre, un « état » : nombre d'écritures, total
crédité, total débité et **net du carnet** (crédits − débits, cohérent avec le
signe affiché sur chaque ligne). Couvre l'épargne collecte + classique (le
carnet COLLECTE, partagé par les deux produits).

Le net d'un carnet ≠ solde du compte : c'est ce qui a transité PAR ce carnet.
"""
from __future__ import annotations

from decimal import Decimal

from apps_coop.members.models import BookletOrder

from .models import ClassicSavingsTransaction, SavingsTransaction
from .serializers import transaction_sens


def member_booklet_summaries(member) -> list[dict]:
    """Liste des états par carnet pour ``member`` (année décroissante).

    Chaque entrée : ``booklet_order`` (id), ``type``, ``type_display``,
    ``annee``, ``count``, ``total_credit``, ``total_debit``, ``solde_net``,
    ``collecte_count`` / ``classique_count`` (ventilation par produit).
    """
    buckets: dict[int, dict] = {}

    def _empty() -> dict:
        return {
            "credit": Decimal("0"),
            "debit": Decimal("0"),
            "count": 0,
            "collecte": 0,
            "classique": 0,
        }

    for model, produit in (
        (SavingsTransaction, "collecte"),
        (ClassicSavingsTransaction, "classique"),
    ):
        rows = (
            model.objects.filter(
                account__member=member, booklet_order__isnull=False
            )
            .values("booklet_order_id", "type_op", "montant")
        )
        for r in rows:
            b = buckets.setdefault(r["booklet_order_id"], _empty())
            montant = Decimal(r["montant"])
            if transaction_sens(r["type_op"]) == "credit":
                b["credit"] += montant
            else:
                b["debit"] += montant
            b["count"] += 1
            b[produit] += 1

    if not buckets:
        return []

    carnets = {
        bo.id: bo
        for bo in BookletOrder.objects.filter(id__in=list(buckets.keys()))
    }
    result = []
    for bid, b in buckets.items():
        bo = carnets.get(bid)
        if bo is None:
            continue
        result.append(
            {
                "booklet_order": bo.id,
                "type": bo.type,
                "type_display": bo.get_type_display(),
                "annee": bo.annee,
                "count": b["count"],
                "collecte_count": b["collecte"],
                "classique_count": b["classique"],
                "total_credit": str(b["credit"]),
                "total_debit": str(b["debit"]),
                "solde_net": str(b["credit"] - b["debit"]),
            }
        )
    # Année décroissante, puis id décroissant (le plus récent d'abord).
    result.sort(key=lambda r: (r["annee"] or 0, r["booklet_order"]), reverse=True)
    return result
