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


def rappel_reinscription_annuelle() -> dict:
    """Alerte douce J-N : prévient les membres dont l'anniversaire annuel
    approche, pour qu'ils sachent qu'une re-souscription est attendue.

    Politique : **non bloquant**. L'événement ``member.reinscription_due``
    est émis (et donc peut être désactivé par l'admin via EXT-5) ; aucun
    statut de membre n'est changé, aucun service n'est suspendu.

    Idempotence naturelle : on cible exactement la date
    ``today = date_derniere_reinscription + 365 - lead_days``. Comme le cron
    tourne 1×/jour, chaque membre ne reçoit qu'un seul rappel par cycle.
    """
    from apps_coop.members.models import Member
    from apps_coop.notifications.events import emit_event

    today = timezone.localdate()
    lead_days = get_int_setting(
        "members.reinscription.lead_days", DEFAULT_LEAD_DAYS
    )
    # Date d'adhésion (ou dernière réinscription) qui rendra la prochaine
    # réinscription due dans exactement ``lead_days`` jours.
    target_anniversary_anchor = today - timedelta(days=365 - lead_days)

    rappels_envoyes = 0
    erreurs = 0

    qs = (
        Member.objects.filter(
            statut=Member.Statut.ACTIF,
            date_derniere_reinscription=target_anniversary_anchor,
        )
        .select_related("user")
    )
    examines = qs.count()

    for member in qs:
        try:
            due_date = member.prochaine_reinscription_due
            emit_event(
                "member.reinscription_due",
                member=member,
                context={
                    "prenom": member.prenom,
                    "numero_membre": member.numero_membre,
                    "date_anniversaire": due_date.isoformat() if due_date else "",
                    "lead_days": lead_days,
                },
            )
            rappels_envoyes += 1
        except Exception:  # noqa: BLE001 — un échec ne casse pas la chaîne
            erreurs += 1
            logger.warning(
                "rappel_reinscription_annuelle — échec member_id=%s",
                member.id,
                exc_info=True,
            )

    summary = {
        "examines": examines,
        "rappels_envoyes": rappels_envoyes,
        "erreurs": erreurs,
        "lead_days": lead_days,
        "target_date": str(target_anniversary_anchor),
    }
    record_audit(
        action="cron.members.reinscription_rappels.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("rappel_reinscription_annuelle summary=%s", summary)
    return summary
