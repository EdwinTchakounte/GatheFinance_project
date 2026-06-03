"""Voie 3 — MICROCAMPAIGN (refonte 2026 §8 / LOT 11).

Fonctions publiques :
  * ``get_active_campaigns(profil_cible=None)`` — campagnes actuellement
    ouvertes (``actif=True`` et fenêtre courante). Filtre optionnel par
    ``profil_cible`` (égalité stricte, casse-insensible).
  * ``is_campaign_open(campaign, today=None)`` — booléen test d'ouverture.
  * ``validate_amount_against_campaign(campaign, montant)`` — checks plafond
    /plancher + quota bénéficiaires. Lève ``ValueError`` en cas d'écart.
  * ``close_campaign(campaign, reason=...)`` — idempotent ; pose
    ``actif=False`` + ``closed_at`` et émet l'event ``microcampaign.closed``.
  * ``close_expired_campaigns()`` — cron daily ; clôture toutes les campagnes
    dont ``date_fin < today`` et ``actif=True``. Renvoie un compteur.

LOT 11 livre la **fondation** : modèle + clôture. La création du Member
TEMPORAIRE + LoanRequest + Loan se branchera dans LOT 12 (eligibility
routing) une fois le routeur des 3 voies en place.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    record as record_audit,
)

from .models import MicrocreditCampaign


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lecture — campagnes actives
# ---------------------------------------------------------------------------


def get_active_campaigns(
    profil_cible: Optional[str] = None,
    *,
    today=None,
) -> QuerySet[MicrocreditCampaign]:
    """Renvoie le QuerySet des campagnes en cours (actives + dans la fenêtre).

    ``profil_cible`` optionnel filtre par profil ciblé (égalité casse-insensible).
    """
    today = today or timezone.localdate()
    qs = MicrocreditCampaign.objects.filter(
        actif=True,
        date_debut__lte=today,
        date_fin__gte=today,
    )
    if profil_cible:
        qs = qs.filter(profil_cible__iexact=profil_cible.strip())
    return qs.order_by("date_fin", "id")


def is_campaign_open(campaign: MicrocreditCampaign, *, today=None) -> bool:
    """True si la campagne accepte de nouvelles demandes aujourd'hui."""
    today = today or timezone.localdate()
    return (
        bool(campaign.actif)
        and campaign.date_debut <= today <= campaign.date_fin
    )


# ---------------------------------------------------------------------------
# Validation amount + quota
# ---------------------------------------------------------------------------


def _beneficiaires_count(campaign: MicrocreditCampaign) -> int:
    """Nombre de bénéficiaires déjà rattachés (Members TEMPORAIRE)."""
    return campaign.beneficiaires.count()


def validate_amount_against_campaign(
    campaign: MicrocreditCampaign,
    montant,
) -> None:
    """Lève ``ValueError`` si le montant viole les bornes ou le quota.

    Vérifications dans l'ordre :
      1. Campagne ouverte.
      2. Montant ∈ [montant_min, montant_max].
      3. Quota bénéficiaires non atteint si ``plafond_beneficiaires`` posé.
    """
    if not is_campaign_open(campaign):
        raise ValueError(
            f"Campagne #{campaign.id} fermée — date_fin={campaign.date_fin}, "
            f"actif={campaign.actif}."
        )

    montant_d = Decimal(montant)
    if montant_d <= 0:
        raise ValueError("Montant demandé doit être strictement positif.")
    if montant_d < Decimal(campaign.montant_min):
        raise ValueError(
            f"Montant {montant_d} < plancher campagne {campaign.montant_min}."
        )
    if montant_d > Decimal(campaign.montant_max):
        raise ValueError(
            f"Montant {montant_d} > plafond campagne {campaign.montant_max}."
        )

    if campaign.plafond_beneficiaires is not None:
        used = _beneficiaires_count(campaign)
        if used >= campaign.plafond_beneficiaires:
            raise ValueError(
                f"Quota bénéficiaires atteint pour campagne #{campaign.id} "
                f"({used}/{campaign.plafond_beneficiaires})."
            )


# ---------------------------------------------------------------------------
# Clôture
# ---------------------------------------------------------------------------


@transaction.atomic
def close_campaign(
    campaign: MicrocreditCampaign,
    *,
    reason: str = "manual",
) -> MicrocreditCampaign:
    """Pose ``actif=False`` + ``closed_at`` + audit. Idempotent."""
    campaign = (
        MicrocreditCampaign.objects.select_for_update().get(pk=campaign.pk)
    )
    if not campaign.actif:
        return campaign

    now = timezone.now()
    campaign.actif = False
    campaign.closed_at = now
    campaign.close_reason = (reason or "manual").strip()[:64]
    campaign.save(update_fields=["actif", "closed_at", "close_reason", "updated_at"])

    record_audit(
        action="microcampaign.closed",
        entite_type="MicrocreditCampaign",
        entite_id=campaign.id,
        details={"reason": campaign.close_reason, "closed_at": now.isoformat()},
    )
    _emit("microcampaign.closed", campaign)
    return campaign


def close_expired_campaigns(*, today=None) -> dict:
    """Cron — clôture toutes les campagnes ``actif=True`` dont la date_fin est passée.

    Renvoie ``{"closed": N, "checked": M}`` pour les logs cron. Idempotent
    (sécurisé pour rejouer le cron plusieurs fois dans la journée).
    """
    today = today or timezone.localdate()
    checked = MicrocreditCampaign.objects.filter(
        actif=True, date_fin__lt=today
    )
    closed = 0
    for campaign in checked:
        try:
            close_campaign(campaign, reason="expired")
            closed += 1
        except Exception:  # noqa: BLE001 — un échec ne doit pas casser le cron
            logger.exception(
                "close_expired_campaigns — échec campaign_id=%s", campaign.pk
            )
    return {"checked": checked.count() if closed == 0 else closed, "closed": closed}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _emit(event_code: str, campaign: MicrocreditCampaign) -> None:
    """Émission best-effort (LOT 11 — pas de template requis)."""
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            event_code,
            member=None,
            context={
                "campagne": campaign.nom,
                "date_fin": str(campaign.date_fin),
                "close_reason": campaign.close_reason or "",
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning(
            "emit_event(%s) a échoué pour campaign #%s", event_code, campaign.id
        )


# get_int_setting is imported in case downstream LOT 12 needs default tunables
# from this module — kept here to keep the import surface stable.
_ = get_int_setting  # noqa: F841 (placeholder, no warn)
