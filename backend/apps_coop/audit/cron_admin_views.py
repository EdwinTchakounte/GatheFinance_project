"""Admin — édition des schedules django-q (cadence des cron jobs).

Permet à l'admin de modifier l'expression cron d'un job (ex. faire passer
``savings.interest.monthly`` de ``"0 2 1 * *"`` (mensuel) à ``"0 */2 * * *"``
(toutes les 2h) pour valider les flows complets en recette — intérêts, emails,
notifications, etc.

Endpoints :
  - GET  /api/v1/audit/admin/cron-schedules/         → liste tous les jobs
  - PATCH /api/v1/audit/admin/cron-schedules/<name>/ → modifie l'expression
  - POST  /api/v1/audit/admin/cron-schedules/<name>/run-now/ → exécute immédiatement
  - POST  /api/v1/audit/admin/cron-schedules/reset-defaults/ → restaure le seed

⚠️ NE PAS exposer en prod réelle aux utilisateurs sans rôle staff senior.
"""
from __future__ import annotations

import importlib
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsStaff

from .services import client_ip, record as record_audit


# Mapping name → expression cron par défaut (synchro avec seed_q_schedules).
# Sert au "reset defaults" pour retrouver l'état initial.
DEFAULT_CRON_BY_NAME = {
    "savings.interest.monthly": "0 2 1 * *",
    "collecte.fin_de_mois": "0 2 1 * *",
    "epargne.anniversary.daily": "30 3 * * *",
    "loans.overdue.daily": "0 3 * * *",
    "loans.due_soon.daily": "0 8 * * *",
    "payments.reconcile.hourly": "0 * * * *",
    "members.reinscription.daily": "0 9 * * *",
    "loans.funding.window_expiry": "*/15 * * * *",
    "loans.microcampaign.close_expired": "15 4 * * *",
    "loans.judicial.auto_escalate": "0 5 * * *",
}


# Presets utiles pour la recette — l'UI peut les proposer en raccourcis.
PRESETS = {
    "Toutes les 2 minutes (test très rapide)": "*/2 * * * *",
    "Toutes les 5 minutes": "*/5 * * * *",
    "Toutes les 15 minutes": "*/15 * * * *",
    "Toutes les heures": "0 * * * *",
    "Toutes les 2 heures": "0 */2 * * *",
    "Tous les jours à 03:00": "0 3 * * *",
    "Hebdomadaire (lundi 02:00)": "0 2 * * 1",
    "Mensuel (1er du mois 02:00)": "0 2 1 * *",
}


def _serialize_schedule(s) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "func": s.func,
        "schedule_type": s.schedule_type,
        "cron": s.cron or "",
        "repeats": s.repeats,
        "next_run": s.next_run.isoformat() if s.next_run else None,
        "default_cron": DEFAULT_CRON_BY_NAME.get(s.name),
        "is_admin_edited": (
            s.name in DEFAULT_CRON_BY_NAME
            and s.cron != DEFAULT_CRON_BY_NAME[s.name]
        ),
    }


@extend_schema(
    tags=["admin"],
    summary="Lister les cron schedules (django-q)",
    description=(
        "Renvoie tous les schedules avec leur cadence actuelle + défaut + flag "
        "is_admin_edited (true si le cron a été modifié par rapport au seed). "
        "Renvoie aussi `presets` pour l'UI."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_cron_schedules_list(request):
    from django_q.models import Schedule

    schedules = Schedule.objects.order_by("name")
    return Response({
        "results": [_serialize_schedule(s) for s in schedules],
        "presets": PRESETS,
    })


@extend_schema(
    tags=["admin"],
    summary="Modifier la cadence d'un cron",
    description=(
        "Body : `{cron: 'minute hour dom month dow'}`. Validation basique "
        "(5 champs). Trace l'action dans l'audit log."
    ),
)
@api_view(["PATCH"])
@permission_classes([IsStaff])
def admin_cron_schedules_update(request, name: str):
    from django_q.models import Schedule

    cron = (request.data.get("cron") or "").strip()
    if not cron:
        return Response(
            {"detail": "Champ `cron` requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Validation minimale : 5 champs séparés par espaces.
    parts = cron.split()
    if len(parts) != 5:
        return Response(
            {"detail": "Expression cron invalide : 5 champs requis (min hour dom mon dow)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        s = Schedule.objects.get(name=name)
    except Schedule.DoesNotExist:
        return Response(
            {"detail": f"Schedule {name!r} introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    old_cron = s.cron
    s.cron = cron
    # Réinitialise next_run pour que django-q recalcule à partir de la nouvelle cron.
    s.next_run = timezone.now()
    s.save(update_fields=["cron", "next_run"])

    record_audit(
        action="admin.cron_schedule.updated",
        entite_type="Schedule",
        entite_id=s.id,
        user=request.user,
        details={"name": s.name, "old_cron": old_cron, "new_cron": cron},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(_serialize_schedule(s))


@extend_schema(
    tags=["admin"],
    summary="Exécuter un cron immédiatement (run-now)",
    description=(
        "Appelle synchronously la fonction associée au schedule — utile pour "
        "tester un cron sans attendre sa prochaine occurrence. Renvoie la "
        "valeur de retour de la tâche."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_cron_schedules_run_now(request, name: str):
    from django_q.models import Schedule

    try:
        s = Schedule.objects.get(name=name)
    except Schedule.DoesNotExist:
        return Response(
            {"detail": f"Schedule {name!r} introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Import dynamique du callable depuis le path "module.func"
    try:
        module_path, func_name = s.func.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
    except (ValueError, ImportError, AttributeError) as exc:
        return Response(
            {"detail": f"Fonction {s.func!r} introuvable : {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        result = func() or {}
    except Exception as exc:  # noqa: BLE001
        record_audit(
            action="admin.cron_schedule.run_failed",
            entite_type="Schedule",
            entite_id=s.id,
            user=request.user,
            details={"name": s.name, "error": str(exc)},
            ip=client_ip(request),
        )
        return Response(
            {"detail": f"Erreur d'exécution : {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    record_audit(
        action="admin.cron_schedule.ran",
        entite_type="Schedule",
        entite_id=s.id,
        user=request.user,
        details={"name": s.name, "summary": result if isinstance(result, dict) else str(result)},
        ip=client_ip(request),
    )
    return Response({
        "name": s.name,
        "executed_at": timezone.now().isoformat(),
        "summary": result if isinstance(result, dict) else {"return": str(result)},
    })


@extend_schema(
    tags=["admin"],
    summary="Restaurer les cadences cron par défaut (seed)",
    description="Remet toutes les schedules connues à leur expression cron d'origine.",
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_cron_schedules_reset_defaults(request):
    from django_q.models import Schedule

    restored = []
    for name, default_cron in DEFAULT_CRON_BY_NAME.items():
        try:
            s = Schedule.objects.get(name=name)
        except Schedule.DoesNotExist:
            continue
        if s.cron != default_cron:
            old = s.cron
            s.cron = default_cron
            s.next_run = timezone.now()
            s.save(update_fields=["cron", "next_run"])
            restored.append({"name": name, "from": old, "to": default_cron})

    record_audit(
        action="admin.cron_schedule.reset_defaults",
        entite_type="Schedule",
        user=request.user,
        details={"restored": restored},
        ip=client_ip(request),
    )
    return Response({"restored": restored, "count": len(restored)})
