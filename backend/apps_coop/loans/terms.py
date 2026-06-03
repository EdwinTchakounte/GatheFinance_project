"""Règles métier du crédit (Règlement Intérieur Gathe Finance 2025).

Source de vérité côté code pour :
  - les paliers de durée en fonction du montant (Article 7) ;
  - le taux d'intérêt d'un crédit (10 % "par transaction", Article 5) ;
  - les taux et modalités de reconduction (Articles 10–12) ;
  - les modalités de paiement (Article 8).

Le règlement officiel est versionné à la racine du repo :
``Reglement_Cooperative_Epargne_Credit (1).docx``. Toute évolution doit être
répercutée ici.
"""
from __future__ import annotations

from decimal import Decimal


# ---------------------------------------------------------------------------
# Article 5 — taux d'intérêt sur les crédits
# ---------------------------------------------------------------------------

#: Taux flat appliqué une fois sur le montant emprunté (pas un taux annuel
#: composé). ``intérêts_totaux = montant × LOAN_INTEREST_RATE``.
LOAN_INTEREST_RATE = Decimal("0.10")


# ---------------------------------------------------------------------------
# Article 7 — durée de remboursement par paliers de montant
# ---------------------------------------------------------------------------

#: Table des paliers ``(montant_min, montant_max, durée_mois)``.
#: ``montant_max`` est inclusif sauf pour la dernière ligne (``None`` = pas de
#: borne haute). Les montants sont exprimés en FCFA.
LOAN_DURATION_TIERS: tuple[tuple[Decimal, Decimal | None, int], ...] = (
    (Decimal("5000"),    Decimal("50000"),  2),
    (Decimal("51000"),   Decimal("200000"), 3),
    (Decimal("201000"),  Decimal("350000"), 4),
    (Decimal("351000"),  Decimal("500000"), 5),
    (Decimal("501000"),  Decimal("650000"), 6),
    (Decimal("651000"),  Decimal("800000"), 7),
    (Decimal("801000"),  Decimal("950000"), 8),
    (Decimal("951000"),  None,              9),
)

MIN_LOAN_AMOUNT = LOAN_DURATION_TIERS[0][0]


def _db_tiers() -> list[tuple[Decimal, Decimal | None, int]] | None:
    """Lit les paliers depuis la table ``LoanDurationTier`` (EXT-2).

    Retourne ``None`` si la table est absente / vide → le code retombe alors
    sur ``LOAN_DURATION_TIERS`` (défaut réglementaire). Ne lève jamais.
    """
    try:
        from .models import LoanDurationTier

        rows = list(
            LoanDurationTier.objects.filter(actif=True)
            .order_by("ordering", "montant_min")
            .values_list("montant_min", "montant_max", "duree_mois")
        )
    except Exception:  # noqa: BLE001 — table non migrée / DB indisponible
        return None
    if not rows:
        return None
    return [(Decimal(lo), None if hi is None else Decimal(hi), int(d)) for lo, hi, d in rows]


def duration_months_for(montant: Decimal) -> int:
    """Renvoie la durée de remboursement (en mois) pour ``montant`` en FCFA.

    Lit en priorité les paliers admin via ``LoanDurationTier`` (EXT-2) ;
    à défaut, retombe sur ``LOAN_DURATION_TIERS`` (Règlement Art. 7).

    Lève ``ValueError`` si le montant est en dessous du minimum réglementaire
    du palier le plus bas.
    """
    tiers = _db_tiers() or list(LOAN_DURATION_TIERS)
    min_amount = tiers[0][0]
    m = Decimal(montant)
    if m < min_amount:
        raise ValueError(
            f"Montant {m} FCFA inférieur au minimum réglementaire "
            f"({min_amount} FCFA)."
        )
    for lo, hi, months in tiers:
        if hi is None or m <= hi:
            if m >= lo:
                return months
            # Montant entre 2 paliers (ex. 50001 entre 50000 et 51000)
            # → palier supérieur (plus de durée = plus de marge).
            return months
    return tiers[-1][2]


# ---------------------------------------------------------------------------
# Article 8 — modalités de paiement (échéances)
# ---------------------------------------------------------------------------

class PaymentModality:
    """Une modalité = la cadence des échéances + le nombre d'échéances par mois.

    Le règlement permet trois modalités. Le choix est définitif sauf demande
    écrite du membre (voir Article 8).
    """

    JOURNALIER = "journalier"
    HEBDOMADAIRE = "hebdomadaire"
    MENSUEL = "mensuel"

    CHOICES = (
        (JOURNALIER,   "Journalier"),
        (HEBDOMADAIRE, "Hebdomadaire"),
        (MENSUEL,      "Mensuel"),
    )

    #: Nombre approximatif d'échéances par mois pour chaque modalité.
    #: Journalier = 30 j ; hebdo ≈ 4.33 → arrondi à 4 (semaine standard).
    INSTALLMENTS_PER_MONTH = {
        JOURNALIER:   30,
        HEBDOMADAIRE: 4,
        MENSUEL:      1,
    }


def _db_modality_installments(code: str) -> int | None:
    """Lit ``installments_per_month`` depuis ``PaymentModalityConfig`` (EXT-2).

    Retourne ``None`` si introuvable / table absente → fallback Python.
    """
    try:
        from .models import PaymentModalityConfig

        val = (
            PaymentModalityConfig.objects.filter(code=code, actif=True)
            .values_list("installments_per_month", flat=True)
            .first()
        )
    except Exception:  # noqa: BLE001
        return None
    return int(val) if val is not None else None


def n_installments(duree_mois: int, modalite: str) -> int:
    """Nombre total d'échéances pour ``(durée, modalité)``.

    Lit en priorité la cadence via ``PaymentModalityConfig`` (EXT-2) ;
    à défaut, retombe sur ``PaymentModality.INSTALLMENTS_PER_MONTH``.
    """
    per_month = _db_modality_installments(modalite)
    if per_month is None:
        try:
            per_month = PaymentModality.INSTALLMENTS_PER_MONTH[modalite]
        except KeyError as exc:
            raise ValueError(f"Modalité inconnue : {modalite!r}") from exc
    return duree_mois * per_month


# ---------------------------------------------------------------------------
# Article 10–12 — reconduction (prorogation)
# ---------------------------------------------------------------------------

#: Délai supplémentaire fixe accordé en cas de reconduction (Article 10).
RENEWAL_EXTRA_MONTHS = 1


class RenewalRate:
    """Trois taux applicables lors d'une reconduction (Article 11)."""

    #: Intérêts versés cash au moment de la reconduction → taux réduit.
    INTERETS_AU_COMPTANT = Decimal("0.10")
    #: Intérêts reportés avec le capital → taux majoré.
    INTERETS_REPORTES = Decimal("0.15")
    #: Pénalité de retard sur les intérêts dus de la somme manquante (Article 12).
    PENALITE_NON_VERSEMENT = Decimal("0.50")
