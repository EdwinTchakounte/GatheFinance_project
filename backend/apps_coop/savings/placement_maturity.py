"""Placement — restitution à échéance (date fixe éditable) + intérêts prorata.

Décision métier 2026-07-17 : tout placement encore **DISPONIBLE** est restitué
avec intérêts à une **date calendaire commune, éditable** (AppSetting, défaut
**1er janvier**). L'intérêt = taux mensuel × montant × (jours depuis le dépôt / 30)
— au prorata du temps immobilisé.

Restituer = créditer les intérêts sur l'épargne classique (écriture
``INTERET_PLACEMENT``) puis passer la tranche à ``LIBEREE`` : le capital, déjà
présent dans le solde classique, redevient librement retirable (il ne compte
plus dans ``solde_placement_actif``).

Les tranches **ENGAGEE** (finançant un crédit) ou **GELEE** (garantie) sont
ignorées ici : elles suivent leur propre cycle et perçoivent leurs intérêts via
le partage 50/50 du crédit. Elles seront restituées à la clôture du crédit.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

_TWO_DP = Decimal("0.01")
DEFAULT_MATURITY_MMDD = "01-01"
# Taux MENSUEL par défaut du placement (tunable). 0.01 = 1 %/mois.
DEFAULT_PLACEMENT_RATE = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def placement_maturity_mmdd() -> str:
    """Date de restitution annuelle au format ``MM-DD`` (défaut 1er janvier)."""
    from apps_coop.audit.services import get_str_setting

    raw = (
        get_str_setting("epargne.placement.maturity_date", DEFAULT_MATURITY_MMDD)
        or ""
    ).strip()
    try:
        m, d = raw.split("-")
        return f"{int(m):02d}-{int(d):02d}"
    except Exception:  # noqa: BLE001 — valeur mal formée → défaut sûr
        return DEFAULT_MATURITY_MMDD


def placement_interest_rate() -> Decimal:
    """Taux mensuel du placement (tunable ``epargne.placement.interest_rate``)."""
    from apps_coop.audit.services import get_str_setting

    try:
        return Decimal(
            get_str_setting(
                "epargne.placement.interest_rate", str(DEFAULT_PLACEMENT_RATE)
            )
        )
    except Exception:  # noqa: BLE001
        return DEFAULT_PLACEMENT_RATE


def is_maturity_day(today: date) -> bool:
    return f"{today.month:02d}-{today.day:02d}" == placement_maturity_mmdd()


def process_placement_maturity(today: date | None = None) -> dict:
    """Restitue toutes les tranches placement DISPONIBLE (intérêts + LIBEREE)."""
    from apps_coop.notifications.events import emit_event

    from .models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        LenderTranche,
    )

    day = today or timezone.now().date()
    rate = placement_interest_rate()
    processed = 0
    total_interest = Decimal("0")

    tranche_ids = list(
        LenderTranche.objects.filter(
            statut=LenderTranche.Statut.DISPONIBLE
        ).values_list("id", flat=True)
    )

    for tid in tranche_ids:
        member = None
        interest = Decimal("0")
        with transaction.atomic():
            locked = (
                LenderTranche.objects.select_for_update()
                .select_related("member")
                .get(pk=tid)
            )
            if locked.statut != LenderTranche.Statut.DISPONIBLE:
                continue
            account = (
                ClassicSavingsAccount.objects.select_for_update()
                .filter(member=locked.member)
                .first()
            )
            if account is None:
                continue

            member = locked.member
            days = max((day - locked.created_at.date()).days, 0)
            interest = _q(
                Decimal(locked.montant) * rate * (Decimal(days) / Decimal(30))
            )
            if interest > 0:
                nouveau_solde = _q(Decimal(account.solde) + interest)
                ClassicSavingsTransaction.objects.create(
                    account=account,
                    payment=None,
                    type_op=ClassicSavingsTransaction.TypeOp.INTERET_PLACEMENT,
                    montant=interest,
                    solde_apres=nouveau_solde,
                    date=timezone.now(),
                )
                account.solde = nouveau_solde
                account.save(update_fields=["solde", "updated_at"])

            locked.statut = LenderTranche.Statut.LIBEREE
            locked.released_at = timezone.now()
            locked.save(update_fields=["statut", "released_at", "updated_at"])
            processed += 1
            total_interest += interest

        # Notification hors transaction (best-effort).
        if member is not None and getattr(member, "user", None) is not None:
            try:
                emit_event(
                    "placement.matured",
                    member=member,
                    context={
                        "prenom": member.prenom or member.nom,
                        "interets": f"{int(interest):,}".replace(",", " "),
                    },
                )
            except Exception:  # noqa: BLE001 — la notif ne bloque jamais le cron
                pass

    return {
        "processed": processed,
        "total_interest": str(total_interest),
        "maturity_mmdd": placement_maturity_mmdd(),
    }
