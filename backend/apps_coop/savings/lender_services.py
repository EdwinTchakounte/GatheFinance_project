"""Services pour la convention prêteur (refonte 2026 §6 — Épargne-prêteur).

Atomiques + idempotents. Toutes les écritures passent par ``select_for_update``
pour éviter les race conditions sur le solde / les tranches.

Cycle de vie côté membre :
  1. ``opt_in_lender`` → crée la convention (mode A global OU mode B tranches)
  2. ``add_tranche``  → optionnel, ajoute une tranche fixe disponible
  3. ``cancel_tranche`` → tranche DISPONIBLE → ANNULEE
  4. ``revoke_consent`` → désactive la convention (impossible si une tranche
                           est encore ENGAGEE dans un crédit vivant)
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import get_int_setting, record as record_audit
from apps_coop.members.models import Member

from .models import LenderConsent, LenderTranche


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration (tunables AppSetting — toutes en XAF / mois)
# ---------------------------------------------------------------------------

def _min_tranche_amount() -> Decimal:
    """Montant minimum d'une tranche, en XAF (tunable ``lender.tranche.min_amount``)."""
    return Decimal(get_int_setting("lender.tranche.min_amount", 5000))


def _min_seniority_months() -> int:
    """Ancienneté min pour pouvoir opt-in (tunable ``lender.consent.min_seniority_months``).

    Défaut 0 = pas de minimum (tout adhérent à jour peut signer). Configurable
    si la coop veut réserver le rôle aux Anciens (≥12m).
    """
    return get_int_setting("lender.consent.min_seniority_months", 0)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

@transaction.atomic
def opt_in_lender(
    *,
    member: Member,
    is_global: bool,
    convention_document=None,
    signed_at=None,
    actor=None,
) -> LenderConsent:
    """Pose le ``LenderConsent`` du membre (1 par membre, idempotent).

    Si une convention **active** existe déjà, on la renvoie telle quelle.
    Si une convention **révoquée** existe, on la **ré-active** (efface
    ``revoked_at`` et met à jour ``is_global``). Cas où le membre revient.

    Args:
      member: le membre signataire.
      is_global: True = Mode A (solde entier prêtable), False = Mode B (tranches).
      convention_document: file-like / ``UploadedFile`` du scan signé.
      signed_at: horodatage de signature (défaut = now).
      actor: user qui pose la convention (pour l'audit).
    """
    # Garde d'ancienneté (tunable, 0 par défaut = no-op).
    min_months = _min_seniority_months()
    if min_months > 0 and member.seniority_months < min_months:
        raise ValueError(
            f"Ancienneté insuffisante : {member.seniority_months} mois "
            f"(minimum {min_months})."
        )

    now = signed_at or timezone.now()

    existing = (
        LenderConsent.objects
        .select_for_update()
        .filter(member=member)
        .first()
    )
    if existing is not None:
        if existing.revoked_at is None:
            # Convention déjà active : idempotent — on peut mettre à jour le
            # mode si demandé mais on ne re-crée pas.
            updated = False
            if existing.is_global != is_global:
                existing.is_global = is_global
                updated = True
            if convention_document is not None:
                existing.convention_document = convention_document
                updated = True
            if updated:
                existing.save(
                    update_fields=["is_global", "convention_document", "updated_at"]
                )
            return existing
        # Réactivation d'un consentement révoqué.
        existing.is_global = is_global
        existing.convention_signed_at = now
        if convention_document is not None:
            existing.convention_document = convention_document
        existing.revoked_at = None
        existing.revoked_by = None
        existing.save(
            update_fields=[
                "is_global",
                "convention_signed_at",
                "convention_document",
                "revoked_at",
                "revoked_by",
                "updated_at",
            ]
        )
        record_audit(
            action="lender.consent.reactivated",
            entite_type="LenderConsent",
            entite_id=existing.id,
            user=actor,
            details={"member_id": member.id, "is_global": is_global},
        )
        return existing

    consent = LenderConsent.objects.create(
        member=member,
        is_global=is_global,
        convention_signed_at=now,
        convention_document=convention_document,
    )
    record_audit(
        action="lender.consent.opt_in",
        entite_type="LenderConsent",
        entite_id=consent.id,
        user=actor,
        details={"member_id": member.id, "is_global": is_global},
    )
    return consent


@transaction.atomic
def add_tranche(
    *,
    member: Member,
    montant: Decimal,
    actor=None,
) -> LenderTranche:
    """Ajoute une tranche DISPONIBLE pour un membre prêteur actif.

    Garde : montant ≥ ``lender.tranche.min_amount`` (tunable).
    Garde : le membre doit avoir un ``LenderConsent`` actif.
    """
    if not member.is_lender:
        raise ValueError(
            "Le membre n'a pas signé la convention prêteur (LenderConsent absent ou révoqué)."
        )

    montant = Decimal(montant)
    min_amount = _min_tranche_amount()
    if montant < min_amount:
        raise ValueError(
            f"Montant tranche trop bas : {montant} XAF (minimum {min_amount} XAF)."
        )

    tranche = LenderTranche.objects.create(
        member=member,
        montant=montant,
        statut=LenderTranche.Statut.DISPONIBLE,
    )
    record_audit(
        action="lender.tranche.created",
        entite_type="LenderTranche",
        entite_id=tranche.id,
        user=actor,
        details={"member_id": member.id, "montant": str(montant)},
    )
    return tranche


# La récupération d'une tranche (DISPONIBLE → ANNULEE) est réservée à l'ADMIN
# et à la révocation de convention (revoke_consent ci-dessous, qui fait sa
# propre bascule). Pas de service `cancel_tranche` exposé au membre.


@transaction.atomic
def revoke_consent(*, member: Member, actor=None) -> LenderConsent:
    """Révoque le consentement prêteur du membre.

    Impossible si **au moins une** tranche est en statut ENGAGEE — il faut
    attendre la clôture des crédits financés (LOT 9 = libération automatique).
    Les tranches DISPONIBLE sont passées en ANNULEE pour cohérence.
    Idempotent : si déjà révoqué, renvoie l'objet.
    """
    consent = (
        LenderConsent.objects
        .select_for_update()
        .filter(member=member)
        .first()
    )
    if consent is None:
        raise ValueError("Aucune convention prêteur à révoquer.")
    if consent.revoked_at is not None:
        return consent  # déjà révoquée — idempotent

    engaged_count = LenderTranche.objects.filter(
        member=member,
        statut=LenderTranche.Statut.ENGAGEE,
    ).count()
    if engaged_count > 0:
        raise ValueError(
            f"Révocation impossible : {engaged_count} tranche(s) encore "
            "engagée(s) dans un crédit en cours."
        )

    now = timezone.now()
    consent.revoked_at = now
    consent.revoked_by = actor if (actor and getattr(actor, "is_authenticated", False)) else None
    consent.save(update_fields=["revoked_at", "revoked_by", "updated_at"])

    # Annulation des tranches DISPONIBLE pour propreté.
    LenderTranche.objects.filter(
        member=member,
        statut=LenderTranche.Statut.DISPONIBLE,
    ).update(statut=LenderTranche.Statut.ANNULEE, updated_at=now)

    record_audit(
        action="lender.consent.revoked",
        entite_type="LenderConsent",
        entite_id=consent.id,
        user=actor,
        details={"member_id": member.id},
    )
    return consent


# ---------------------------------------------------------------------------
# Helpers (utilisés par LOT 8 funding et LOT 9 split intérêts)
# ---------------------------------------------------------------------------

def active_lenders_with_capacity() -> Iterable[Member]:
    """Membres prêteurs actifs ayant ``capacite_pretable > 0``.

    Utilisé par l'algorithme d'allocation funding (LOT 8). Renvoie un
    ``Iterable[Member]`` — pas un QuerySet, parce que la capacité dépend
    d'agrégations qui ne sont pas exprimables en SQL pur (mode A mélange
    solde + tranches engagées).
    """
    consents = LenderConsent.objects.filter(revoked_at__isnull=True).select_related("member")
    for c in consents:
        if c.member.capacite_pretable > 0:
            yield c.member
