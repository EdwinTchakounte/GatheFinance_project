"""Saisie multi-source (refonte 2026 §9.2 / LOT 13 — R1 étendu).

Orchestrateur de la **phase C** (saisie automatique au passage en
``CONTENTIEUX``). Refactor majeur de la R1 legacy 2025 (collecte uniquement,
borrower uniquement) en un sweep ordonné multi-source qui :

  * **Exclut** les ``LenderTranche.ENGAGEE`` du débit (§7 Q5 : la garantie
    active d'un autre crédit n'est pas saisissable).
  * **Inclut** l'épargne de l'avaliste si ``LoanRequest.avaliste`` est posé
    (§9.2 / Q9.4 — la garantie morale devient effective).
  * **Applique au prorata** : pour chaque source, ``min(restant_dû,
    seizable)`` ; transaction ledger + décrément solde ; passe à la source
    suivante jusqu'à épuisement du restant_dû ou des sources.

**Tunables admin** (libre arbitre) :

  - ``loans.seizure.source_order`` (csv) — ordre des sources. Défaut
    ``"borrower_classique,borrower_collecte,avaliste_classique,avaliste_collecte"``.
    Une source absente = ignorée.
  - ``loans.seizure.include_avaliste`` (true) — kill-switch garantie avaliste.
  - ``loans.seizure.exclude_engaged_tranches`` (true) — protection Q5.

API publique : ``seize_for_loan(loan)`` — renvoie un dict détaillé. Le legacy
``seize_member_savings_for_loan`` est conservé comme façade pour
``apps_coop.loans.tasks`` (signature stable, summary dict compatible).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps_coop.audit.services import (
    get_str_setting,
    record as record_audit,
)
from apps_coop.members.models import Member


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables admin
# ---------------------------------------------------------------------------


_DEFAULT_SOURCE_ORDER = (
    "borrower_classique,borrower_collecte,"
    "avaliste_classique,avaliste_collecte"
)
_VALID_SOURCES = {
    "borrower_classique",
    "borrower_collecte",
    "avaliste_classique",
    "avaliste_collecte",
}


def _source_order() -> list[str]:
    raw = get_str_setting("loans.seizure.source_order", _DEFAULT_SOURCE_ORDER)
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    filtered = [p for p in parts if p in _VALID_SOURCES]
    return filtered or list(_DEFAULT_SOURCE_ORDER.split(","))


def _bool_setting(key: str, default: bool = True) -> bool:
    raw = (
        get_str_setting(key, "true" if default else "false") or ""
    ).strip().lower()
    return raw in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Soldes saisissables — exclut LenderTranche.ENGAGEE (Q5)
# ---------------------------------------------------------------------------


def _engaged_tranches_total(member: Member) -> Decimal:
    """Somme des tranches prêteur ``ENGAGEE`` du membre (à exclure de l'épargne classique saisissable)."""
    if not _bool_setting("loans.seizure.exclude_engaged_tranches", True):
        return Decimal("0")
    try:
        from apps_coop.savings.models import LenderTranche

        s = (
            LenderTranche.objects.filter(
                member=member, statut=LenderTranche.Statut.ENGAGEE
            )
            .aggregate(s=Sum("montant"))["s"]
        )
        return Decimal(s or 0)
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _seizable_classique(member: Member) -> Decimal:
    """Solde épargne classique - tranches engagées (Q5)."""
    try:
        if not hasattr(member, "classic_savings_account"):
            return Decimal("0")
        solde = Decimal(member.classic_savings_account.solde)
    except Exception:  # noqa: BLE001
        return Decimal("0")
    engaged = _engaged_tranches_total(member)
    return max(Decimal("0"), solde - engaged)


def _seizable_collecte(member: Member) -> Decimal:
    """Solde compte de collecte journalière (pas de tranche associée — toujours saisissable)."""
    try:
        from apps_coop.savings.models import SavingsAccount

        sa = SavingsAccount.objects.filter(member=member).first()
        if sa is None:
            return Decimal("0")
        return max(Decimal("0"), Decimal(sa.solde))
    except Exception:  # noqa: BLE001
        return Decimal("0")


# ---------------------------------------------------------------------------
# Application — par source
# ---------------------------------------------------------------------------


@dataclass
class _LegResult:
    source: str
    montant: Decimal = Decimal("0")
    solde_avant: Decimal = Decimal("0")
    solde_apres: Decimal = Decimal("0")
    no_op_reason: str = ""


def _seize_from_collecte(
    member: Member, due: Decimal, source_label: str
) -> _LegResult:
    """Débite le compte de collecte (SavingsAccount) — SavingsTransaction.RETRAIT_FORCE."""
    from apps_coop.savings.models import SavingsAccount, SavingsTransaction

    try:
        account = SavingsAccount.objects.select_for_update().get(member=member)
    except SavingsAccount.DoesNotExist:
        return _LegResult(source=source_label, no_op_reason="pas_de_compte_collecte")
    solde = Decimal(account.solde)
    montant = min(solde, due)
    if montant <= 0:
        return _LegResult(
            source=source_label,
            solde_avant=solde,
            solde_apres=solde,
            no_op_reason="solde_nul",
        )
    nouveau = solde - montant
    SavingsTransaction.objects.create(
        account=account,
        payment=None,
        type_op=SavingsTransaction.TypeOp.RETRAIT_FORCE,
        montant=montant,
        solde_apres=nouveau,
        date=timezone.now(),
    )
    account.solde = nouveau
    account.save(update_fields=["solde", "updated_at"])
    return _LegResult(
        source=source_label,
        montant=montant,
        solde_avant=solde,
        solde_apres=nouveau,
    )


def _seize_from_classique(
    member: Member, due: Decimal, source_label: str
) -> _LegResult:
    """Débite le compte épargne classique — ClassicSavingsTransaction.RETRAIT_FORCE.

    Exclusion ``LenderTranche.ENGAGEE`` appliquée via ``_seizable_classique``.
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    if not hasattr(member, "classic_savings_account"):
        return _LegResult(source=source_label, no_op_reason="pas_de_compte_classique")

    account = ClassicSavingsAccount.objects.select_for_update().get(
        member=member
    )
    solde = Decimal(account.solde)
    seizable = _seizable_classique(member)
    montant = min(seizable, due)
    if montant <= 0:
        return _LegResult(
            source=source_label,
            solde_avant=solde,
            solde_apres=solde,
            no_op_reason="solde_seizable_nul",
        )
    nouveau = solde - montant
    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=None,
        type_op=ClassicSavingsTransaction.TypeOp.RETRAIT_FORCE,
        montant=montant,
        solde_apres=nouveau,
        date=timezone.now(),
    )
    account.solde = nouveau
    account.save(update_fields=["solde", "updated_at"])
    return _LegResult(
        source=source_label,
        montant=montant,
        solde_avant=solde,
        solde_apres=nouveau,
    )


# ---------------------------------------------------------------------------
# Orchestrateur principal
# ---------------------------------------------------------------------------


@dataclass
class SeizureResult:
    """Détail structuré retourné par ``seize_for_loan``."""

    saisie_totale: Decimal = Decimal("0")
    saisie_borrower: Decimal = Decimal("0")
    saisie_avaliste: Decimal = Decimal("0")
    solde_restant_apres: Decimal = Decimal("0")
    poursuite_engagee: bool = False
    no_op: bool = False
    legs: list[_LegResult] = field(default_factory=list)

    def to_summary(self) -> dict:
        """Format compatible avec l'ancienne signature ``seize_member_savings_for_loan``.

        Conserve les clés legacy ``saisie``, ``epargne_apres``,
        ``solde_restant_apres``, ``poursuite``, ``no_op`` + ajoute les détails
        multi-source pour les nouveaux consommateurs.
        """
        # epargne_apres = solde résiduel sur le compte borrower_collecte
        # (compat avec les logs cron qui s'attendent à cette clé).
        borrower_collecte_leg = next(
            (l for l in self.legs if l.source == "borrower_collecte"),
            None,
        )
        epargne_apres = (
            borrower_collecte_leg.solde_apres
            if borrower_collecte_leg is not None
            else Decimal("0")
        )
        return {
            "saisie": self.saisie_totale,
            "saisie_borrower": self.saisie_borrower,
            "saisie_avaliste": self.saisie_avaliste,
            "epargne_apres": epargne_apres,
            "solde_restant_apres": self.solde_restant_apres,
            "poursuite": self.poursuite_engagee,
            "no_op": self.no_op,
            "legs": [
                {
                    "source": leg.source,
                    "montant": str(leg.montant),
                    "solde_avant": str(leg.solde_avant),
                    "solde_apres": str(leg.solde_apres),
                    "no_op_reason": leg.no_op_reason,
                }
                for leg in self.legs
            ],
        }


@transaction.atomic
def seize_for_loan(loan) -> SeizureResult:
    """Saisie multi-source d'un Loan en CONTENTIEUX (idempotent).

    Boucle sur ``loans.seizure.source_order`` (configurable admin) ; pour
    chaque source, applique ``min(due, seizable)``. Stoppe dès que la dette
    est soldée. Sinon, pose ``poursuite_judiciaire_at`` et garde le reliquat
    pour le contentieux humain (LOT 14 / phase D).
    """
    from .models import Loan

    locked: Loan = Loan.objects.select_for_update().select_related(
        "member", "loan_request__avaliste"
    ).get(pk=loan.pk)

    if locked.epargne_saisie_at is not None:
        # Idempotent : déjà passé.
        return SeizureResult(
            no_op=True,
            solde_restant_apres=Decimal(locked.solde_restant),
        )

    due = Decimal(locked.solde_restant)
    if due <= 0:
        now = timezone.now()
        locked.epargne_saisie_at = now
        locked.epargne_saisie_montant = Decimal("0")
        locked.save(
            update_fields=[
                "epargne_saisie_at",
                "epargne_saisie_montant",
                "updated_at",
            ]
        )
        return SeizureResult(no_op=True, solde_restant_apres=Decimal("0"))

    borrower = locked.member
    avaliste: Optional[Member] = getattr(
        locked.loan_request, "avaliste", None
    )
    include_avaliste = _bool_setting("loans.seizure.include_avaliste", True)
    if not include_avaliste:
        avaliste = None

    result = SeizureResult()
    remaining = due
    order = _source_order()

    for source in order:
        if remaining <= 0:
            break

        if source == "borrower_classique":
            leg = _seize_from_classique(borrower, remaining, source)
            result.saisie_borrower += leg.montant
        elif source == "borrower_collecte":
            leg = _seize_from_collecte(borrower, remaining, source)
            result.saisie_borrower += leg.montant
        elif source == "avaliste_classique":
            if avaliste is None:
                continue
            leg = _seize_from_classique(avaliste, remaining, source)
            result.saisie_avaliste += leg.montant
        elif source == "avaliste_collecte":
            if avaliste is None:
                continue
            leg = _seize_from_collecte(avaliste, remaining, source)
            result.saisie_avaliste += leg.montant
        else:
            continue

        result.legs.append(leg)
        if leg.montant > 0:
            result.saisie_totale += leg.montant
            remaining -= leg.montant

    # Mise à jour du Loan
    nouveau_restant = max(Decimal("0"), due - result.saisie_totale)
    now = timezone.now()
    locked.epargne_saisie_at = now
    locked.epargne_saisie_montant = result.saisie_totale
    locked.solde_restant = nouveau_restant

    poursuite = nouveau_restant > 0
    if poursuite:
        locked.poursuite_judiciaire_at = now
    if nouveau_restant == 0:
        from .models import Loan as LoanModel

        locked.statut = LoanModel.Statut.CLOTURE

    locked.save(
        update_fields=[
            "solde_restant",
            "epargne_saisie_at",
            "epargne_saisie_montant",
            "poursuite_judiciaire_at",
            "statut",
            "updated_at",
        ]
    )

    result.solde_restant_apres = nouveau_restant
    result.poursuite_engagee = poursuite

    record_audit(
        action="loan.savings_seized",
        entite_type="Loan",
        entite_id=locked.id,
        details={
            # ``saisie`` reste la clé legacy attendue par les logs/observabilité
            # 2025. ``saisie_totale`` est l'alias refactor (lisible).
            "saisie": str(result.saisie_totale),
            "saisie_totale": str(result.saisie_totale),
            "saisie_borrower": str(result.saisie_borrower),
            "saisie_avaliste": str(result.saisie_avaliste),
            "due_avant": str(due),
            "solde_restant_apres": str(nouveau_restant),
            "poursuite_engagee": poursuite,
            "avaliste_member_id": avaliste.id if avaliste else None,
            "legs": [
                {
                    "source": leg.source,
                    "montant": str(leg.montant),
                    "no_op_reason": leg.no_op_reason,
                }
                for leg in result.legs
            ],
        },
    )
    return result
