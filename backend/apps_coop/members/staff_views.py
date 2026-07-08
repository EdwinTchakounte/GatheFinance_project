"""Gestion des utilisateurs *staff* et des rôles RBAC (admin dashboard).

Endpoints (tous gated ``ResourceAccess("access")`` — donc superuser/admin, ou
un compte à qui on a délégué la ressource « access ») :

  GET/POST   admin/access/resources/      → registre des ressources (onglets)
  GET/POST   admin/access/roles/          → liste / création de rôles
  PATCH/DEL  admin/access/roles/<pk>/     → mise à jour / suppression d'un rôle
  GET/POST   admin/access/users/          → liste / création d'utilisateurs staff
  PATCH/DEL  admin/access/users/<pk>/     → mise à jour / désactivation d'un user
"""
from __future__ import annotations

import secrets
import string

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record

from .access import effective_resources, has_full_access
from .models import StaffRole
from .permissions import GROUP_ADMIN, GROUP_COMITE, GROUP_STAFF, ResourceAccess
from .resources import resources_payload, valid_resources

STAFF_GROUPS = [GROUP_ADMIN, GROUP_COMITE, GROUP_STAFF]


def _log(request, action, entite_id=None, details=None):
    record(
        action=action,
        entite_type="staff",
        entite_id=entite_id,
        user=request.user,
        details=details or {},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


# --------------------------------------------------------------------------- #
# Sérialisation légère
# --------------------------------------------------------------------------- #
def _role_row(role: StaffRole) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "resources": valid_resources(role.resources),
        "users_count": role.users.count(),
    }


def _user_row(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "groups": list(user.groups.values_list("name", flat=True)),
        "role_ids": list(user.staff_roles.values_list("id", flat=True)),
        "roles": list(user.staff_roles.values_list("name", flat=True)),
        "resources": sorted(effective_resources(user)),
        "full_access": has_full_access(user),
    }


def _gen_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# --------------------------------------------------------------------------- #
# Ressources
# --------------------------------------------------------------------------- #
@api_view(["GET"])
@permission_classes([ResourceAccess("access")])
def access_resources(request):
    return Response({"results": resources_payload()})


# --------------------------------------------------------------------------- #
# Rôles
# --------------------------------------------------------------------------- #
@api_view(["GET", "POST"])
@permission_classes([ResourceAccess("access")])
def access_roles(request):
    if request.method == "GET":
        rows = [_role_row(r) for r in StaffRole.objects.all()]
        return Response({"results": rows})

    data = request.data
    name = (data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Le nom du rôle est requis."}, status=400)
    if StaffRole.objects.filter(name__iexact=name).exists():
        return Response({"detail": "Un rôle porte déjà ce nom."}, status=400)
    role = StaffRole.objects.create(
        name=name,
        description=(data.get("description") or "").strip(),
        resources=valid_resources(data.get("resources") or []),
    )
    _log(request, "staff_role.create", role.id, {"name": role.name})
    return Response(_role_row(role), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([ResourceAccess("access")])
def access_role_detail(request, pk: int):
    try:
        role = StaffRole.objects.get(pk=pk)
    except StaffRole.DoesNotExist:
        return Response({"detail": "Rôle introuvable."}, status=404)

    if request.method == "DELETE":
        role.users.clear()
        rid = role.id
        role.delete()
        _log(request, "staff_role.delete", rid)
        return Response(status=204)

    data = request.data
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            return Response({"detail": "Le nom du rôle est requis."}, status=400)
        if StaffRole.objects.filter(name__iexact=name).exclude(pk=role.pk).exists():
            return Response({"detail": "Un rôle porte déjà ce nom."}, status=400)
        role.name = name
    if "description" in data:
        role.description = (data.get("description") or "").strip()
    if "resources" in data:
        role.resources = valid_resources(data.get("resources") or [])
    role.save()
    _log(request, "staff_role.update", role.id)
    return Response(_role_row(role))


# --------------------------------------------------------------------------- #
# Utilisateurs staff
# --------------------------------------------------------------------------- #
def _apply_roles(user: User, role_ids) -> None:
    if role_ids is None:
        return
    roles = list(StaffRole.objects.filter(id__in=list(role_ids)))
    user.staff_roles.set(roles)


@api_view(["GET", "POST"])
@permission_classes([ResourceAccess("access")])
def access_users(request):
    if request.method == "GET":
        qs = (
            User.objects.filter(Q(is_staff=True) | Q(groups__name__in=STAFF_GROUPS))
            .exclude(member__isnull=False)
            .distinct()
            .order_by("email")
            .prefetch_related("groups", "staff_roles")
        )
        return Response({"results": [_user_row(u) for u in qs]})

    data = request.data
    email = (data.get("email") or "").strip().lower()
    if not email:
        return Response({"detail": "L'e-mail est requis."}, status=400)
    if User.objects.filter(username__iexact=email).exists() or User.objects.filter(
        email__iexact=email
    ).exists():
        return Response({"detail": "Un utilisateur avec cet e-mail existe déjà."}, status=400)

    password = data.get("password") or ""
    generated = False
    if not password:
        password = _gen_password()
        generated = True
    elif len(password) < 8:
        return Response({"detail": "Le mot de passe doit faire au moins 8 caractères."}, status=400)

    # Groupe de base (passe IsStaff ; les rôles affinent l'accès). Seul un
    # compte à accès total peut attribuer le groupe `admin` (= accès total) —
    # empêche un délégué « access » de créer un compte plus puissant que lui.
    base_group = (data.get("group") or GROUP_STAFF).strip()
    if base_group not in STAFF_GROUPS:
        base_group = GROUP_STAFF
    if base_group == GROUP_ADMIN and not has_full_access(request.user):
        return Response(
            {"detail": "Seul un administrateur peut attribuer le groupe « admin »."},
            status=403,
        )

    with transaction.atomic():
        user = User.objects.create(
            username=email,
            email=email,
            first_name=(data.get("first_name") or "").strip(),
            last_name=(data.get("last_name") or "").strip(),
            is_staff=True,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        grp, _ = Group.objects.get_or_create(name=base_group)
        user.groups.add(grp)
        _apply_roles(user, data.get("role_ids"))

    _log(request, "staff_user.create", user.id, {"email": email})
    row = _user_row(user)
    if generated:
        # Mot de passe montré UNE seule fois à l'admin créateur.
        row["temporary_password"] = password
    return Response(row, status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([ResourceAccess("access")])
def access_user_detail(request, pk: int):
    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        return Response({"detail": "Utilisateur introuvable."}, status=404)

    if request.method == "DELETE":
        # On ne supprime pas (intégrité audit) : on désactive.
        if user.id == request.user.id:
            return Response({"detail": "Impossible de désactiver son propre compte."}, status=400)
        user.is_active = False
        user.save(update_fields=["is_active"])
        _log(request, "staff_user.deactivate", user.id)
        return Response(_user_row(user))

    data = request.data
    updated = []
    if "first_name" in data:
        user.first_name = (data.get("first_name") or "").strip()
        updated.append("first_name")
    if "last_name" in data:
        user.last_name = (data.get("last_name") or "").strip()
        updated.append("last_name")
    if "is_active" in data:
        if user.id == request.user.id and not data.get("is_active"):
            return Response({"detail": "Impossible de se désactiver soi-même."}, status=400)
        user.is_active = bool(data.get("is_active"))
        updated.append("is_active")
    if updated:
        user.save(update_fields=updated)

    resp_extra = {}
    if "role_ids" in data:
        _apply_roles(user, data.get("role_ids"))
    if "group" in data:
        base_group = (data.get("group") or "").strip()
        # Seul un compte à accès total peut promouvoir au groupe `admin`
        # (empêche l'auto-promotion / l'escalade par un délégué « access »).
        if base_group == GROUP_ADMIN and not has_full_access(request.user):
            return Response(
                {"detail": "Seul un administrateur peut attribuer le groupe « admin »."},
                status=403,
            )
        if base_group in STAFF_GROUPS:
            user.groups.remove(*user.groups.filter(name__in=STAFF_GROUPS))
            grp, _ = Group.objects.get_or_create(name=base_group)
            user.groups.add(grp)
    if data.get("reset_password"):
        new_pwd = _gen_password()
        user.set_password(new_pwd)
        user.save(update_fields=["password"])
        resp_extra["temporary_password"] = new_pwd

    _log(request, "staff_user.update", user.id)
    return Response({**_user_row(user), **resp_extra})
