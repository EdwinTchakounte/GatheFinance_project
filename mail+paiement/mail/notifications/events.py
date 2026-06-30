"""Moteur d'événements métier — point d'entrée unique ``emit_event`` (EXT-5).

Principe de dissociation **définition ↔ exécution** :

  - Le code métier (services, views, crons) **émet** un événement nommé via
    ``emit_event("member.activated", member=m, context={...})``. Il ne sait
    ni à qui envoyer quoi, ni si c'est actif.

  - La **définition** vit en base : ``EventConfig`` décrit chaque type
    d'événement (label, status, sensitive), et ``EventHook`` décrit les
    actions à exécuter (envoyer tel template, audit seulement, etc.).

  - Un admin peut donc activer / couper / brancher de nouvelles actions
    **sans déploiement** et sans toucher au code métier.

Garanties :

  - ``emit_event`` ne lève **jamais** d'exception (best-effort, comme
    ``send_template``). Si la table n'est pas seedée, on dégrade gracieusement
    en passant directement par ``send_template`` (rétrocompat avec le code
    existant — voir docstring de ``_fallback_send``).
  - Toute exécution est **tracée** via ``record_audit`` : émission,
    skip volontaire (BLOCKED / OPTIONAL inactif), succès des hooks.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def emit_event(
    code: str,
    *,
    member: Any = None,
    context: dict | None = None,
    attachments: list | None = None,
    to_email: str | None = None,
) -> dict:
    """Émet l'événement métier ``code``.

    Lit ``EventConfig`` pour décider si l'événement doit être traité, puis
    déclenche chaque ``EventHook(active=True)`` lié.

    L'adresse e-mail des hooks EMAIL provient par défaut de
    ``member.user.email`` ; ``to_email`` permet de la surcharger pour les
    événements **pré-Member** (ex. rejet d'une demande d'adhésion : le
    candidat n'a pas encore de User).

    Renvoie un résumé ``{"fired": bool, "hooks_run": int, "reason": str}``
    pour permettre aux callers d'incrémenter leurs compteurs sans avoir à
    relire la base. Ne lève jamais.
    """
    summary: dict = {"fired": False, "hooks_run": 0, "reason": ""}
    ctx = context or {}

    # Import paresseux (évite les cycles à l'import du module).
    try:
        from apps_coop.audit.services import record as record_audit
        from .models import EventConfig, EventHook
        from .services import send_template
    except Exception:  # pragma: no cover — apps non chargées
        logger.exception("emit_event(%s) — import failure", code)
        summary["reason"] = "import_error"
        return summary

    # 1) Lookup de la config — fallback gracieux si la table n'est pas migrée
    #    ou si le code n'est pas seedé : on tente quand même d'envoyer un
    #    template du même nom (rétrocompat avec le code pré-EXT-5).
    try:
        cfg = EventConfig.objects.get(code=code)
    except EventConfig.DoesNotExist:
        logger.warning(
            "emit_event(%s) — EventConfig absent, fallback send_template direct",
            code,
        )
        result = _fallback_send(
            code, member=member, context=ctx, attachments=attachments,
            to_email=to_email,
        )
        summary["fired"] = result is not None
        summary["hooks_run"] = 1 if result is not None else 0
        summary["reason"] = "fallback_no_config"
        return summary
    except Exception:  # noqa: BLE001 — table absente / DB hiccup
        logger.exception("emit_event(%s) — DB indisponible", code)
        result = _fallback_send(
            code, member=member, context=ctx, attachments=attachments,
            to_email=to_email,
        )
        summary["fired"] = result is not None
        summary["hooks_run"] = 1 if result is not None else 0
        summary["reason"] = "fallback_db_error"
        return summary

    # 2) Statut → exécuter ou skipper ?
    if not cfg.is_effective:
        reason = (
            "blocked" if cfg.status == EventConfig.Status.BLOCKED
            else "optional_inactive"
        )
        try:
            record_audit(
                action="event.skipped",
                entite_type="EventConfig",
                entite_id=cfg.id,
                user=getattr(member, "user", None) if member else None,
                details={"code": code, "reason": reason, "status": cfg.status},
            )
        except Exception:  # pragma: no cover
            logger.exception("audit du skip event a échoué")
        summary["reason"] = reason
        return summary

    # 3) Exécution des hooks actifs (ordre stable via ``ordering``).
    hooks_run = 0
    for hook in cfg.hooks.filter(active=True).order_by("ordering"):
        try:
            if hook.action_type == EventHook.ActionType.EMAIL:
                template_code = hook.target_template_code or code
                # Préférence : to_email explicite (cas pré-Member) > member.user.email.
                recipient = to_email or (
                    member.user.email
                    if member and getattr(getattr(member, "user", None), "email", None)
                    else None
                )
                if recipient:
                    send_template(
                        template_code,
                        to=recipient,
                        member=member,
                        context=ctx,
                        attachments=attachments,
                    )
                    hooks_run += 1
                else:
                    logger.info(
                        "emit_event(%s) hook EMAIL — pas d'email destinataire",
                        code,
                    )
            elif hook.action_type == EventHook.ActionType.AUDIT_ONLY:
                hooks_run += 1  # l'audit final ci-dessous suffit
        except Exception:  # pragma: no cover — un hook ne casse pas la chaîne
            logger.exception(
                "emit_event(%s) — hook id=%s a échoué", code, hook.id
            )

    # 4) Audit de l'émission (toujours, même si 0 hook actif).
    try:
        record_audit(
            action=f"event.{code}",
            entite_type="EventConfig",
            entite_id=cfg.id,
            user=getattr(member, "user", None) if member else None,
            details={"code": code, "hooks_run": hooks_run, "status": cfg.status},
        )
    except Exception:  # pragma: no cover
        logger.exception("audit de l'événement a échoué")

    summary["fired"] = True
    summary["hooks_run"] = hooks_run
    summary["reason"] = "ok"
    return summary


def _fallback_send(
    code: str,
    *,
    member: Any,
    context: dict,
    attachments: list | None,
    to_email: str | None = None,
):
    """Tentative best-effort quand ``EventConfig`` n'est pas (encore) seedé.

    Permet à un déploiement en cours (table créée mais seed pas encore
    exécuté) de continuer à envoyer les e-mails — on traite alors ``code``
    comme un code de template direct. Respecte ``to_email`` explicite
    (cas pré-Member type rejet d'adhésion / welcome avec email d'inscription).
    """
    from .services import send_template

    recipient = to_email or (
        member.user.email
        if member and getattr(getattr(member, "user", None), "email", None)
        else None
    )
    if not recipient:
        return None
    return send_template(
        code,
        to=recipient,
        member=member,
        context=context,
        attachments=attachments,
    )
