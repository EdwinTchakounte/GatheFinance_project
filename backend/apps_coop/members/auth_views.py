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
    from .access import effective_resources, has_full_access

    member = getattr(user, "member", None)
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "groups": list(user.groups.values_list("name", flat=True)),
        # RBAC — ressources (onglets admin) accessibles + accès total ?
        "resources": sorted(effective_resources(user)),
        "full_access": has_full_access(user),
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


# ─────────────────────────────────────────────────────────────────────────────
# Mot de passe oublié — flow OTP 6 chiffres par e-mail
# ─────────────────────────────────────────────────────────────────────────────

class _PasswordResetThrottle(ScopedRateThrottle):
    scope = "auth-password-reset"


def _hash_code(code: str) -> str:
    """SHA-256 hex du code clair. Pas de salt — l'attaquant a déjà l'e-mail."""
    import hashlib

    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@extend_schema(
    tags=["auth"],
    summary="Demander un code de réinitialisation de mot de passe",
    description=(
        "Génère un code OTP 6 chiffres expirant en 15 minutes et l'envoie par "
        "e-mail (template `auth.password_reset_otp`). Anti-énumération : "
        "renvoie toujours 200 même si l'e-mail n'existe pas. Throttle : 5/h/IP."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["email"],
            "properties": {"email": {"type": "string", "format": "email"}},
        }
    },
    responses={200: OpenApiResponse(description="Code envoyé (réponse opaque)")},
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([_PasswordResetThrottle])
def request_password_reset(request):
    import secrets
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from .models import PasswordResetCode

    email = (request.data.get("email") or "").strip().lower()
    if not email:
        # On reste opaque même sur l'erreur de format (anti-énumération).
        return Response({"detail": "Si un compte existe, un code a été envoyé."})

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        record(
            action="auth.password_reset.requested_unknown",
            entite_type="User",
            entite_id=None,
            details={"email": email},
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return Response({"detail": "Si un compte existe, un code a été envoyé."})

    # Invalide les codes précédents non utilisés.
    PasswordResetCode.objects.filter(
        user=user, used_at__isnull=True,
    ).update(used_at=timezone.now())

    code = f"{secrets.randbelow(1_000_000):06d}"
    PasswordResetCode.objects.create(
        user=user,
        code_hash=_hash_code(code),
        expires_at=timezone.now() + timedelta(minutes=15),
        ip_request=client_ip(request),
    )

    # Envoi e-mail Brevo. Best-effort : on n'expose rien si le mail échoue
    # (le membre verra qu'aucun mail n'arrive et pourra retenter).
    try:
        from apps_coop.notifications.services import send_template

        send_template(
            "auth.password_reset_otp",
            to=user.email,
            context={
                "prenom": (
                    getattr(getattr(user, "member", None), "prenom", None)
                    or user.first_name
                    or ""
                ),
                "code": code,
                "ttl_minutes": 15,
            },
            member=getattr(user, "member", None),
        )
    except Exception:  # noqa: BLE001 — best-effort
        import logging

        logging.getLogger(__name__).exception(
            "send_template(auth.password_reset_otp) failed for user=%s", user.id,
        )

    record(
        action="auth.password_reset.requested",
        entite_type="User",
        entite_id=user.id,
        details={"email": email},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response({"detail": "Si un compte existe, un code a été envoyé."})


@extend_schema(
    tags=["auth"],
    summary="Confirmer la réinitialisation avec un code OTP",
    description=(
        "Vérifie le code OTP reçu par e-mail puis change le mot de passe. "
        "Le code expire 15 min après émission, est consommé au 1er succès, "
        "et plafonné à 5 essais. Throttle : 5/h/IP."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["email", "code", "new_password"],
            "properties": {
                "email": {"type": "string", "format": "email"},
                "code": {"type": "string", "minLength": 6, "maxLength": 6},
                "new_password": {"type": "string", "format": "password"},
            },
        }
    },
    responses={
        200: OpenApiResponse(description="Mot de passe réinitialisé"),
        400: OpenApiResponse(description="Code invalide, expiré ou mot de passe trop faible"),
    },
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([_PasswordResetThrottle])
def confirm_password_reset(request):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    from .models import PasswordResetCode

    email = (request.data.get("email") or "").strip().lower()
    code = (request.data.get("code") or "").strip()
    new_password = request.data.get("new_password") or ""

    # Réponse générique pour ne pas distinguer "email inconnu" de "code faux".
    invalid = Response(
        {"detail": "Code invalide ou expiré."},
        status=status.HTTP_400_BAD_REQUEST,
    )

    if not (email and code and new_password):
        return invalid
    if len(code) != 6 or not code.isdigit():
        return invalid

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return invalid

    # On prend le code actif le plus récent.
    record_qs = PasswordResetCode.objects.filter(
        user=user, used_at__isnull=True, expires_at__gt=timezone.now(),
    ).order_by("-created_at")
    reset = record_qs.first()
    if reset is None or reset.attempts >= 5:
        return invalid

    if reset.code_hash != _hash_code(code):
        reset.attempts += 1
        if reset.attempts >= 5:
            reset.used_at = timezone.now()
        reset.save(update_fields=["attempts", "used_at"])
        record(
            action="auth.password_reset.failed_attempt",
            entite_type="User",
            entite_id=user.id,
            details={"attempts": reset.attempts},
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return invalid

    # Validation du nouveau mot de passe (longueur, complexité Django).
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return Response(
            {"detail": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    reset.used_at = timezone.now()
    reset.ip_confirm = client_ip(request)
    reset.save(update_fields=["used_at", "ip_confirm"])

    record(
        action="auth.password_reset.completed",
        entite_type="User",
        entite_id=user.id,
        details={},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response({"detail": "Mot de passe réinitialisé."})


# ─────────────────────────────────────────────────────────────────────────────
# PWD Option B — Setup mot de passe initial (token usage unique 72h)
# ─────────────────────────────────────────────────────────────────────────────


def _mask_email(email: str) -> str:
    """Renvoie ``j***@domain.tld`` pour la page de confirmation."""
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}***@{domain}"


@extend_schema(
    tags=["auth"],
    summary="Vérifier un token de définition de mot de passe",
    description=(
        "Vérifie qu'un token reçu dans l'e-mail de bienvenue est encore valide "
        "(non utilisé, non expiré). Renvoie un payload `{email_mask, expires_at}` "
        "pour la page de confirmation. 410 si expiré/utilisé, 404 si inconnu."
    ),
    responses={
        200: OpenApiResponse(description="Token valide → `{email_mask, expires_at}`"),
        404: OpenApiResponse(description="Token inconnu"),
        410: OpenApiResponse(description="Token expiré ou déjà utilisé"),
    },
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_password_setup_token(request):
    from .models import PasswordSetupToken

    token_value = (request.query_params.get("token") or "").strip()
    if not token_value:
        return Response({"detail": "Token requis."}, status=status.HTTP_400_BAD_REQUEST)

    token = PasswordSetupToken.objects.filter(token=token_value).first()
    if token is None:
        return Response({"detail": "Lien invalide."}, status=status.HTTP_404_NOT_FOUND)
    if token.is_consumed or token.is_expired:
        return Response(
            {"detail": "Lien expiré ou déjà utilisé. Demande un nouveau lien à l'agence."},
            status=status.HTTP_410_GONE,
        )

    return Response({
        "email_mask": _mask_email(token.user.email),
        "expires_at": token.expires_at.isoformat(),
    })


@extend_schema(
    tags=["auth"],
    summary="Définir le mot de passe initial via token",
    description=(
        "Consomme un token reçu dans l'e-mail de bienvenue et pose le mot de "
        "passe. Validé par les validateurs Django (longueur, complexité). Le "
        "token est marqué utilisé — toute réutilisation est refusée. "
        "Throttle : 5/h/IP."
    ),
    request={
        "application/json": {
            "type": "object",
            "required": ["token", "password"],
            "properties": {
                "token": {"type": "string"},
                "password": {"type": "string", "format": "password"},
            },
        }
    },
    responses={
        200: OpenApiResponse(description="Mot de passe défini → `{email}` (pour redirect login)"),
        400: OpenApiResponse(description="Mot de passe invalide"),
        404: OpenApiResponse(description="Token inconnu"),
        410: OpenApiResponse(description="Token expiré ou déjà utilisé"),
    },
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([_PasswordResetThrottle])
def confirm_password_setup(request):
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from django.utils import timezone

    from .models import PasswordSetupToken

    token_value = (request.data.get("token") or "").strip()
    new_password = request.data.get("password") or ""

    if not token_value or not new_password:
        return Response(
            {"detail": "Token et mot de passe requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token = PasswordSetupToken.objects.filter(token=token_value).select_related("user").first()
    if token is None:
        return Response({"detail": "Lien invalide."}, status=status.HTTP_404_NOT_FOUND)
    if token.is_consumed or token.is_expired:
        return Response(
            {"detail": "Lien expiré ou déjà utilisé."},
            status=status.HTTP_410_GONE,
        )

    user = token.user
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        return Response(
            {"detail": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=["password"])
    token.used_at = timezone.now()
    token.ip_confirm = client_ip(request)
    token.save(update_fields=["used_at", "ip_confirm"])

    record(
        action="auth.password_setup.completed",
        entite_type="User",
        entite_id=user.id,
        details={},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response({"detail": "Mot de passe défini.", "email": user.email})
