"""Role-based permission classes for the cooperative API.

Staff roles live in Django groups (`admin`, `comite`, `staff`); the member
profile is a OneToOne on `User`. We expose three high-level classes used by
viewsets:

  - `IsMember`         user has an attached Member profile
  - `IsStaff`          user is in any internal group (admin, comite, staff)
  - `IsAdmin`          user is in the `admin` group (super-rights inside the coop)
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission


GROUP_ADMIN = "admin"
GROUP_COMITE = "comite"
GROUP_STAFF = "staff"


def _in_group(user, name: str) -> bool:
    return bool(user and user.is_authenticated and user.groups.filter(name=name).exists())


class IsMember(BasePermission):
    """User has a member profile — covers ``actif`` AND ``suspendu``.

    Use this for read-only endpoints and for the 1st-cotisation payment init,
    where a suspended member *needs* portal access to activate their account.
    For mutating endpoints that require an active member (deposit, repayment,
    loan request, …), use :class:`IsActiveMember` instead.
    """

    message = "Profil membre requis."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(
            u
            and u.is_authenticated
            and hasattr(u, "member")
            and u.member.statut in {"actif", "suspendu"}
        )


class IsActiveMember(BasePermission):
    """User has a member profile **and** the member is ``actif``."""

    message = "Compte membre suspendu — paye ta 1re cotisation pour l'activer."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(
            u
            and u.is_authenticated
            and hasattr(u, "member")
            and u.member.statut == "actif"
        )


class IsStaff(BasePermission):
    """User is part of any internal staff group (admin / comite / staff)."""

    message = "Accès réservé au personnel."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(
            u
            and u.is_authenticated
            and (
                u.is_superuser
                or u.groups.filter(name__in=[GROUP_ADMIN, GROUP_COMITE, GROUP_STAFF]).exists()
            )
        )


class IsAdmin(BasePermission):
    """Highest internal role — for sensitive operations (close a member,
    overwrite a balance, change app settings).
    """

    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or _in_group(u, GROUP_ADMIN)))


class IsComite(BasePermission):
    """Credit committee — instructs and decides on loan requests."""

    message = "Accès réservé au comité crédit."

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or _in_group(u, GROUP_COMITE)))
