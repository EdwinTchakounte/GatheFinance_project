"""Admin API — consulter le journal d'audit (AuditLog).

Le ``AuditMiddleware`` et les appels ``services.record(...)`` ecrivent en
permanence dans ``AuditLog``. Jusqu'ici, ces lignes etaient seulement
accessibles via le Django admin classique (``/admin/coop_audit/auditlog/``).
Ce module expose une API REST staff-only pour les afficher dans le
dashboard Next.js, avec pagination + filtres.

Routes :

  - ``GET /api/v1/audit/admin/logs/`` — liste paginee + filtres
"""
from __future__ import annotations

from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import IsStaff

from .models import AuditLog


MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


def _parse_int(value, default: int, lo: int = 0, hi: int | None = None) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    if v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


def _parse_date(value) -> datetime | None:
    """Accept 'YYYY-MM-DD' (date) ou ISO datetime."""
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        # Date simple → 00:00:00 timezone aware
        if len(raw) == 10:
            d = datetime.strptime(raw, "%Y-%m-%d").date()
            return timezone.make_aware(datetime.combine(d, time.min))
        # ISO datetime
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except (TypeError, ValueError):
        return None


def _serialize_user(user) -> dict | None:
    if user is None:
        return None
    full = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return {
        "id": user.pk,
        "email": user.email or user.username,
        "full_name": full or (user.email or user.username),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
    }


def _serialize_log(log: AuditLog) -> dict:
    return {
        "id": log.pk,
        "action": log.action,
        "entite_type": log.entite_type or "",
        "entite_id": log.entite_id,
        "user": _serialize_user(log.user),
        "ip": log.ip or "",
        "user_agent": log.user_agent or "",
        "details_json": log.details_json or {},
        "created_at": log.created_at.isoformat(),
    }


@extend_schema(
    tags=["audit"],
    summary="Journal d'audit — liste paginee + filtres (admin)",
    description=(
        "Renvoie les entrees du journal d'audit (`AuditLog`) avec filtres "
        "et pagination offset/limit. Toutes les mutations API (POST/PUT/PATCH/"
        "DELETE) y sont tracees automatiquement via `AuditMiddleware`, et les "
        "events metier critiques (decision credit, validation paiement, "
        "changement config) y sont enregistres explicitement via "
        "`services.record(...)`.\n\n"
        "**Filtres supportes** :\n"
        "- `q` — recherche dans action / entite_type / email utilisateur\n"
        "- `user` — id de l'utilisateur (0 = systeme / cron)\n"
        "- `action` — match exact ou prefixe (ex. `loan.` matche tous les events credit)\n"
        "- `entite_type` — match exact (ex. `Loan`, `Payment`, `AppSetting`)\n"
        "- `entite_id` — match exact\n"
        "- `date_from`, `date_to` — bornes (format YYYY-MM-DD ou ISO datetime)\n"
        "- `limit` (defaut 25, max 100), `offset` (defaut 0)"
    ),
    responses={200: OpenApiResponse(description="`{count, results: [...] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_audit_logs_list(request):
    qp = request.query_params
    limit = _parse_int(qp.get("limit"), DEFAULT_PAGE_SIZE, lo=1, hi=MAX_PAGE_SIZE)
    offset = _parse_int(qp.get("offset"), 0, lo=0)

    qs = AuditLog.objects.select_related("user").order_by("-created_at")

    # --- Filtres -------------------------------------------------------------
    q_search = (qp.get("q") or "").strip()
    if q_search:
        qs = qs.filter(
            Q(action__icontains=q_search)
            | Q(entite_type__icontains=q_search)
            | Q(user__email__icontains=q_search)
            | Q(user__username__icontains=q_search)
        )

    user_raw = (qp.get("user") or "").strip()
    if user_raw:
        if user_raw == "0":
            qs = qs.filter(user__isnull=True)
        else:
            try:
                qs = qs.filter(user_id=int(user_raw))
            except ValueError:
                return Response(
                    {"detail": "Parametre 'user' doit etre un entier (0 = systeme)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    action = (qp.get("action") or "").strip()
    if action:
        # Permet 'loan.' pour matcher tous les events credit
        if action.endswith("."):
            qs = qs.filter(action__startswith=action)
        else:
            qs = qs.filter(action=action)

    entite_type = (qp.get("entite_type") or "").strip()
    if entite_type:
        qs = qs.filter(entite_type=entite_type)

    entite_id_raw = (qp.get("entite_id") or "").strip()
    if entite_id_raw:
        try:
            qs = qs.filter(entite_id=int(entite_id_raw))
        except ValueError:
            return Response(
                {"detail": "Parametre 'entite_id' doit etre un entier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    date_from = _parse_date(qp.get("date_from"))
    if date_from:
        qs = qs.filter(created_at__gte=date_from)

    date_to = _parse_date(qp.get("date_to"))
    if date_to:
        # date_to inclus la journee entiere si c'est une date simple
        if len(str(qp.get("date_to")).strip()) == 10:
            date_to = date_to + timezone.timedelta(days=1)
        qs = qs.filter(created_at__lt=date_to)

    count = qs.count()
    page = list(qs[offset : offset + limit])

    return Response(
        {
            "count": count,
            "limit": limit,
            "offset": offset,
            "results": [_serialize_log(log) for log in page],
        }
    )


@extend_schema(
    tags=["audit"],
    summary="Facettes du journal d'audit (actions et entite_types distincts)",
    description=(
        "Renvoie les valeurs distinctes des champs `action` et `entite_type` "
        "pour peupler les filtres deroulants de l'UI admin."
    ),
    responses={200: OpenApiResponse(description="`{actions: [...], entite_types: [...]}`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_audit_logs_facets(request):
    actions = list(
        AuditLog.objects.order_by("action")
        .values_list("action", flat=True)
        .distinct()
    )
    entite_types = list(
        AuditLog.objects.exclude(entite_type="")
        .order_by("entite_type")
        .values_list("entite_type", flat=True)
        .distinct()
    )
    return Response({"actions": actions, "entite_types": entite_types})
