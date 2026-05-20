"""Public form endpoints, consumed by the Next.js front-end.

Layers of abuse protection: a server-issued signed math captcha, a honeypot
field, and per-IP rate limiting (DRF ScopedRateThrottle, scope "form-submit").
On success a notification e-mail is sent to the Gathe Finance inbox and an
acknowledgement to the visitor (Brevo SMTP).
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps_coop.members.serializers import MembershipPublicSerializer

from . import emails
from .captcha import new_challenge
from .serializers import ContactSerializer, NewsletterSerializer


class FormSubmitThrottle(ScopedRateThrottle):
    scope = "form-submit"


def _request_meta(request) -> dict:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    return {"ip_address": ip or None, "user_agent": request.META.get("HTTP_USER_AGENT", "")[:400]}


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def captcha_challenge(_request):
    """Return a fresh signed math challenge: {"question": "3 + 4", "token": "..."}."""
    return Response(new_challenge())


def _handle_submission(request, serializer_class, kind: str):
    serializer = serializer_class(
        data=request.data,
        context={"request": request, "request_meta": _request_meta(request)},
    )
    serializer.is_valid(raise_exception=True)

    # Honeypot: pretend success, do nothing.
    if serializer.context.get("honeypot_tripped"):
        return Response({"ok": True}, status=status.HTTP_201_CREATED)

    obj = serializer.save()
    payload = {
        "name": getattr(obj, "name", ""),
        "city": getattr(obj, "city", ""),
        "phone": getattr(obj, "phone", ""),
        "email": getattr(obj, "email", ""),
        "message": getattr(obj, "message", ""),
        "language": getattr(obj, "language", "fr"),
    }
    try:
        emails.notify_team(kind, payload)
        emails.acknowledge(kind, payload)
    except Exception:  # noqa: BLE001 - never fail the request because of e-mail issues
        import logging

        logging.getLogger(__name__).exception("Form notification e-mail failed for %s", kind)
    return Response({"ok": True}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([FormSubmitThrottle])
def contact(request):
    return _handle_submission(request, ContactSerializer, "contact")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([FormSubmitThrottle])
def membership(request):
    # Writes to apps_coop.members.MembershipRequest. Instruction (approve /
    # reject) happens from the Django admin — see apps_coop.members.services.
    return _handle_submission(request, MembershipPublicSerializer, "membership")


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([FormSubmitThrottle])
def newsletter(request):
    serializer = NewsletterSerializer(data=request.data, context={})
    serializer.is_valid(raise_exception=True)
    if serializer.context.get("honeypot_tripped"):
        return Response({"ok": True}, status=status.HTTP_201_CREATED)
    serializer.save()
    return Response({"ok": True}, status=status.HTTP_201_CREATED)
