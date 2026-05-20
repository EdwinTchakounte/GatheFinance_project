"""Audit middleware — logs a coarse `http.<method>` AuditLog row for every
mutation hitting the cooperative API (`/api/v1/`).

Service-layer code should still call `apps_coop.audit.services.record()` for
finer business events; this middleware exists to guarantee a baseline trail
even when a developer forgets the explicit call.
"""
from __future__ import annotations

from .services import client_ip, record


SENSITIVE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
AUDITED_PREFIX = "/api/v1/"
# Login / logout are audited explicitly with richer payloads by the views.
SKIP_PATH_PREFIXES = ("/api/v1/auth/",)


class AuditMiddleware:
    """Log every mutating request under /api/v1/ that isn't already audited."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if (
            request.method in SENSITIVE_METHODS
            and path.startswith(AUDITED_PREFIX)
            and not path.startswith(SKIP_PATH_PREFIXES)
            and 200 <= response.status_code < 400
        ):
            record(
                action=f"http.{request.method.lower()}",
                entite_type="http",
                user=getattr(request, "user", None),
                details={
                    "path": path,
                    "status": response.status_code,
                },
                ip=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        return response
