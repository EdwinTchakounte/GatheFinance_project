"""Admin — vue « Supervision » (observabilité ops).

Agrège en lecture seule ce qu'un admin doit surveiller d'un coup d'œil :
  - santé backend + base de données ;
  - planificateur django-q (nb de schedules, prochaine exécution, succès/échecs 24h) ;
  - messages e-mail envoyés par le système (``EmailLog``) — stats + liste paginée.
    ⚠️ Le système n'envoie PAS de SMS : le canal est l'e-mail (Brevo). On surface
    donc les e-mails, sans inventer un canal SMS inexistant.
  - lien vers le monitoring conteneurs (Beszel, sous-domaine ``monitor.*``),
    piloté par le setting/env ``MONITOR_URL`` (vide = non configuré).

Endpoints :
  - GET /api/v1/audit/admin/supervision/         → overview (santé + stats + liens)
  - GET /api/v1/audit/admin/supervision/emails/  → liste paginée des EmailLog

Gated par la ressource RBAC ``supervision`` (cf. members/resources.py).
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.members.permissions import ResourceAccess
from apps_coop.notifications.models import EmailLog

_EMAILS_PAGE_SIZE = 25

# Raccourcis vers les ressources ops clés (le frontend filtre selon le RBAC).
_QUICK_LINKS = [
    {"label": "Journal d'audit", "href": "/audit", "resource": "audit"},
    {"label": "Planification (cron)", "href": "/cron-schedules", "resource": "cron-schedules"},
    {"label": "Paramètres", "href": "/app-settings", "resource": "app-settings"},
    {"label": "Coûts", "href": "/costs", "resource": "costs"},
    {"label": "Campagnes", "href": "/campaigns", "resource": "campaigns"},
    {"label": "Support membres", "href": "/support", "resource": "support"},
]


def _scheduler_summary(since_24h) -> dict:
    """Résumé django-q : nb de schedules, prochaine exécution, succès/échecs 24h."""
    try:
        from django_q.models import Failure, Schedule, Success
    except Exception as exc:  # noqa: BLE001 — django-q absent / non configuré
        return {"available": False, "error": str(exc)}

    schedules = list(Schedule.objects.order_by("next_run"))
    next_runs = [s.next_run for s in schedules if s.next_run]
    return {
        "available": True,
        "schedules": len(schedules),
        "next_run": min(next_runs).isoformat() if next_runs else None,
        "success_24h": Success.objects.filter(started__gte=since_24h).count(),
        "failed_24h": Failure.objects.filter(started__gte=since_24h).count(),
        "upcoming": [
            {
                "name": s.name,
                "cron": s.cron or "",
                "next_run": s.next_run.isoformat() if s.next_run else None,
            }
            for s in schedules[:6]
        ],
    }


@extend_schema(
    tags=["admin"],
    summary="Supervision — overview (santé, planificateur, e-mails, liens)",
)
@api_view(["GET"])
@permission_classes([ResourceAccess("supervision")])
def admin_supervision_overview(request):
    now = timezone.now()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    # Santé base de données (le backend répond forcément puisqu'on est ici).
    db_ok = True
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception:  # noqa: BLE001
        db_ok = False

    def _ecount(**kw) -> int:
        return EmailLog.objects.filter(**kw).count()

    emails = {
        "total": EmailLog.objects.count(),
        "sent_7d": _ecount(statut=EmailLog.Statut.ENVOYE, created_at__gte=since_7d),
        "failed_7d": _ecount(statut=EmailLog.Statut.ECHEC, created_at__gte=since_7d),
        "pending": _ecount(statut=EmailLog.Statut.EN_ATTENTE),
        "failed_total": _ecount(statut=EmailLog.Statut.ECHEC),
    }

    return Response(
        {
            "generated_at": now.isoformat(),
            "health": {"backend": True, "database": db_ok},
            "scheduler": _scheduler_summary(since_24h),
            "emails": emails,
            # Monitoring conteneurs (Beszel) — externe, ouvert dans un onglet.
            "monitor_url": getattr(settings, "MONITOR_URL", "") or "",
            "quick_links": _QUICK_LINKS,
        }
    )


@extend_schema(
    tags=["admin"],
    summary="Supervision — messages e-mail envoyés (EmailLog paginé)",
)
@api_view(["GET"])
@permission_classes([ResourceAccess("supervision")])
def admin_supervision_emails(request):
    qs = EmailLog.objects.select_related("member").order_by("-created_at")

    statut = (request.GET.get("statut") or "").strip()
    if statut in dict(EmailLog.Statut.choices):
        qs = qs.filter(statut=statut)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(destinataire__icontains=q)

    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    total = qs.count()
    start = (page - 1) * _EMAILS_PAGE_SIZE
    rows = list(qs[start : start + _EMAILS_PAGE_SIZE])

    def _member_name(r) -> str | None:
        if not r.member_id:
            return None
        m = r.member
        full = f"{m.nom} {m.prenom}".strip()
        return full or m.numero_membre

    results = [
        {
            "id": r.id,
            "destinataire": r.destinataire,
            "objet": r.objet,
            "template": r.template_id,
            "statut": r.statut,
            "statut_display": r.get_statut_display(),
            "erreur": r.erreur,
            "member": _member_name(r),
            "created_at": r.created_at.isoformat(),
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
        }
        for r in rows
    ]

    return Response(
        {
            "results": results,
            "count": total,
            "page": page,
            "page_size": _EMAILS_PAGE_SIZE,
            "has_next": start + _EMAILS_PAGE_SIZE < total,
        }
    )
