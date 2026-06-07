"""Session auth endpoints for the cooperative app — used by both portal
(member) and admin (staff) frontends.

Endpoints:
  GET  /api/v1/auth/csrf/    → primes the CSRF cookie (call before any POST)
  POST /api/v1/auth/login/   → {email, password} → 200 with user + member info, or 401
  POST /api/v1/auth/logout/  → destroys the session
  GET  /api/v1/auth/me/      → returns current user identity (or 401)

Both portal and admin use the same login route; the response payload tells
the frontend whether the user is a member, staff, or both.
"""
from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps_coop.audit.services import client_ip, record


def _user_payload(user) -> dict:
    """Compact identity payload returned by /me and /login."""
    member = getattr(user, "member", None)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "groups": list(user.groups.values_list("name", flat=True)),
        "member": (
            {
                "id": member.id,
                "numero_membre": member.numero_membre,
                "nom": member.nom,
                "prenom": member.prenom,
                "statut": member.statut,
                "phone": member.phone,
                "date_adhesion": member.date_adhesion.isoformat(),
            }
            if member is not None
            else None
        ),
    }


@extend_schema(
    tags=["auth"],
    summary="Prime le cookie CSRF",
    description=(
        "À appeler une fois au démarrage du SPA pour poser le cookie `csrftoken` "
        "(SameSite=Lax). Sa valeur est ensuite envoyée dans l'en-tête `X-CSRFToken` "
        "des requêtes mutantes (POST/PUT/PATCH/DELETE)."
    ),
    responses={200: OpenApiResponse(description="`{ \"csrfToken\": \"...\" }` + Set-Cookie csrftoken")},
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def csrf_prime(request):
    """Ensures the CSRF cookie is set on the client. SPAs call this once on boot."""
    return Response({"csrfToken": get_token(request)})


class _LoginThrottle(ScopedRateThrottle):
    scope = "auth-login"


@extend_schema(
    tags=["auth"],
    summary="Connexion session (cookie HttpOnly)",
    description=(
        "Échange un couple `email` + `password` contre une session Django. "
        "Pose le cookie `gathe_sessionid` (HttpOnly, SameSite=Lax). Throttle : 20/h/IP."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["email", "password"],
            "properties": {
                "email": {"type": "string", "format": "email"},
                "password": {"type": "string", "format": "password"},
            },
        }
    },
    responses={
        200: OpenApiResponse(description="Identité du user connecté (cf. /auth/me/)"),
        400: OpenApiResponse(description="Email ou mot de passe manquant"),
        401: OpenApiResponse(description="Identifiants invalides"),
    },
    examples=[
        OpenApiExample(
            "Login member",
            value={"email": "marie.tankam@test.local", "password": "test1234"},
            request_only=True,
        ),
    ],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([_LoginThrottle])
def login_view(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""
    if not email or not password:
        return Response(
            {"detail": "Email et mot de passe requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # We look up by email — `authenticate` accepts `username`, so map first.
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        username = User.objects.values_list("username", flat=True).get(email__iexact=email)
    except User.DoesNotExist:
        username = email  # let authenticate fail naturally; avoids account enumeration

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        record(
            action="auth.login.failed",
            entite_type="User",
            details={"email": email},
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return Response({"detail": "Identifiants invalides."}, status=status.HTTP_401_UNAUTHORIZED)

    login(request, user)
    record(
        action="auth.login.success",
        entite_type="User",
        entite_id=user.id,
        user=user,
        details={"session_age_seconds": request.session.get_expiry_age()},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(_user_payload(user))


@extend_schema(
    tags=["auth"],
    summary="Déconnexion",
    description="Détruit la session Django et le cookie associé.",
    responses={204: OpenApiResponse(description="Session terminée")},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    user_id = request.user.id
    logout(request)
    record(
        action="auth.logout",
        entite_type="User",
        entite_id=user_id,
        details={},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["auth"],
    summary="Identité du user connecté",
    description=(
        "Renvoie le payload `{id, email, first_name, last_name, is_staff, "
        "is_superuser, groups, member}` où `member` est non-null pour un "
        "membre et null pour un staff interne."
    ),
    responses={200: OpenApiResponse(description="Identité courante")},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(_user_payload(request.user))


class _PasswordThrottle(ScopedRateThrottle):
    scope = "auth-login"


@extend_schema(
    tags=["auth"],
    summary="Changer son mot de passe",
    description=(
        "Le membre/staff connecté change son mot de passe en fournissant "
        "`current_password` + `new_password`. Validé par les validateurs Django "
        "(longueur, complexité). La session reste active grâce au re-hash. "
        "Throttle : 20/h/IP."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["current_password", "new_password"],
            "properties": {
                "current_password": {"type": "string", "format": "password"},
                "new_password": {"type": "string", "format": "password"},
            },
        }
    },
    responses={
        200: OpenApiResponse(description="Mot de passe modifié"),
        400: OpenApiResponse(description="Mot de passe actuel faux ou nouveau invalide"),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([_PasswordThrottle])
def change_password(request):
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError

    current = request.data.get("current_password") or ""
    new = request.data.get("new_password") or ""
    user = request.user

    if not user.check_password(current):
        return Response(
            {"detail": "Mot de passe actuel incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        validate_password(new, user=user)
    except ValidationError as exc:
        return Response(
            {"detail": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new)
    user.save(update_fields=["password"])
    # Garde la session active après changement de mot de passe.
    update_session_auth_hash(request, user)

    record(
        action="auth.password_changed",
        entite_type="User",
        entite_id=user.id,
        details={},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response({"detail": "Mot de passe modifié."})
