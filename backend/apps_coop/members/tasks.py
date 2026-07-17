"""Crons du domaine ``members`` — exécutés par ``qcluster`` (django-q2).

A2 — Réinscription annuelle (alerte douce, non bloquante).
Configurable via les ``AppSetting`` (EXT-1) :
  - ``members.reinscription.lead_days`` (défaut 30)
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    record as record_audit,
)


logger = logging.getLogger(__name__)


#: Défaut réglementaire (alerte douce envoyée ``DEFAULT_LEAD_DAYS`` avant
#: l'anniversaire annuel). Modifiable via ``AppSetting.members.reinscription.lead_days``.
DEFAULT_LEAD_DAYS = 30
#: D2 . Periode de grace apres l'anniversaire avant suspension auto.
#: Décision 2026-07-17 (G5) : J+10 — tout membre non ré-inscrit passe INACTIF
#: 10 jours après la clôture du cycle. Tunable ``members.reinscription.grace_days``.
DEFAULT_GRACE_DAYS = 10


def rappel_reinscription_annuelle() -> dict:
    """D2 . Cron unifie qui couvre les 4 phases du cycle annuel :

      . J-30 : rappel doux (member.reinscription_due)
      . J-7  : rappel urgent (member.reinscription_due_urgent)
      . J+0  : rappel anniversaire (member.reinscription_due_today)
      . J+grace (default 30) : suspension auto + email
        (member.reinscription_expired_suspended)

    Idempotence naturelle : chaque phase cible une date precise relative a
    ``date_derniere_reinscription``. Comme le cron tourne 1x/jour, chaque
    membre ne recoit qu'un seul rappel par phase et par cycle.
    """
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event

    today = timezone.localdate()
    lead_days = get_int_setting("members.reinscription.lead_days", DEFAULT_LEAD_DAYS)
    grace_days = get_int_setting("members.reinscription.grace_days", DEFAULT_GRACE_DAYS)

    # 4 phases . dates ancrage qui rendent J-30 / J-7 / J0 / J+grace today.
    anchor_j30 = today - timedelta(days=365 - lead_days)   # J-30
    anchor_j7 = today - timedelta(days=358)                # J-7
    anchor_j0 = today - timedelta(days=365)                # J+0 (anniversaire)
    anchor_grace = today - timedelta(days=365 + grace_days)  # J+grace (= suspension)

    summary = {
        "rappels_j30": 0, "rappels_j7": 0, "rappels_j0": 0,
        "suspensions": 0, "erreurs": 0,
        "lead_days": lead_days, "grace_days": grace_days,
    }

    # Phase 1-3 : envoi rappels pour membres ACTIF.
    phases = [
        (anchor_j30, "member.reinscription_due", "rappels_j30"),
        (anchor_j7, "member.reinscription_due_urgent", "rappels_j7"),
        (anchor_j0, "member.reinscription_due_today", "rappels_j0"),
    ]
    for anchor, event_code, counter in phases:
        qs = (
            Member.objects.filter(
                statut=Member.Statut.ACTIF,
                date_derniere_reinscription=anchor,
            )
            .select_related("user")
        )
        for member in qs:
            try:
                due_date = member.prochaine_reinscription_due
                emit_event(
                    event_code,
                    member=member,
                    context={
                        "prenom": member.prenom,
                        "numero_membre": member.numero_membre,
                        "date_anniversaire": due_date.isoformat() if due_date else "",
                        "lead_days": lead_days,
                        "grace_days": grace_days,
                    },
                )
                summary[counter] += 1
            except Exception:  # noqa: BLE001
                summary["erreurs"] += 1
                logger.warning(
                    "rappel_reinscription_annuelle . echec phase=%s member_id=%s",
                    event_code, member.id, exc_info=True,
                )

    # Phase 4 : suspension auto (J+grace). On suspend les ACTIF dont la
    # date_derniere_reinscription est <= anchor_grace (capture aussi les
    # cas ou le cron a saute un jour).
    suspend_qs = (
        Member.objects.filter(
            statut=Member.Statut.ACTIF,
            date_derniere_reinscription__lte=anchor_grace,
        )
        .select_related("user")
    )
    for member in suspend_qs:
        try:
            previous_statut = member.statut
            member.statut = Member.Statut.SUSPENDU
            member.save(update_fields=["statut", "updated_at"])
            record_audit(
                action="member.suspended_non_renewal",
                entite_type="Member",
                entite_id=member.id,
                details={
                    "previous_statut": previous_statut,
                    "anchor": member.date_derniere_reinscription.isoformat()
                    if member.date_derniere_reinscription else None,
                    "grace_days": grace_days,
                    "trigger": "cron.rappel_reinscription_annuelle",
                },
            )
            try:
                emit_event(
                    "member.reinscription_expired_suspended",
                    member=member,
                    context={
                        "prenom": member.prenom,
                        "numero_membre": member.numero_membre,
                        "grace_days": grace_days,
                        "anchor": member.date_derniere_reinscription.isoformat()
                        if member.date_derniere_reinscription else "",
                    },
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "emit suspension event echec member_id=%s",
                    member.id, exc_info=True,
                )
            summary["suspensions"] += 1
        except Exception:  # noqa: BLE001
            summary["erreurs"] += 1
            logger.warning(
                "rappel_reinscription_annuelle . suspension echec member_id=%s",
                member.id, exc_info=True,
            )

    record_audit(
        action="cron.members.reinscription_rappels.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("rappel_reinscription_annuelle summary=%s", summary)
    return summary
