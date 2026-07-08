"""Résolution de l'accès RBAC effectif d'un utilisateur staff.

Règle (voir aussi ``members.resources`` et le design RBAC) :

  * superuser **ou** groupe ``admin``           → accès TOTAL (jamais verrouillé) ;
  * sinon, utilisateur avec des ``StaffRole``    → union des ressources des rôles ;
  * sinon, staff/comité *legacy* sans rôle       → accès TOTAL (rétro-compat) ;
  * sinon                                        → aucun accès.

On ne verrouille jamais les comptes existants (admin, ou staff/comité sans rôle
assigné) : la restriction ne s'applique qu'aux utilisateurs à qui on a
explicitement donné un ou plusieurs rôles.
"""
from __future__ import annotations

from .permissions import GROUP_ADMIN, GROUP_COMITE, GROUP_STAFF
from .resources import RESOURCE_KEYS, valid_resources


def _has_full_access(user) -> bool:
    return bool(user.is_superuser or user.groups.filter(name=GROUP_ADMIN).exists())


def _is_legacy_staff(user) -> bool:
    return user.groups.filter(name__in=[GROUP_COMITE, GROUP_STAFF]).exists()


def effective_resources(user) -> set[str]:
    """Ensemble des clés de ressources auxquelles ``user`` a accès.

    Retourne l'ensemble complet ``RESOURCE_KEYS`` pour les accès totaux.
    """
    if not (user and user.is_authenticated):
        return set()
    if _has_full_access(user):
        return set(RESOURCE_KEYS)
    roles = list(user.staff_roles.all())
    if roles:
        granted: set[str] = set()
        for role in roles:
            granted.update(valid_resources(role.resources))
        return granted
    # Staff/comité historique sans rôle assigné → on garde l'accès complet.
    if _is_legacy_staff(user):
        return set(RESOURCE_KEYS)
    return set()


def has_full_access(user) -> bool:
    """True si l'utilisateur a accès à toutes les ressources."""
    if not (user and user.is_authenticated):
        return False
    if _has_full_access(user):
        return True
    if user.staff_roles.exists():
        return False
    return _is_legacy_staff(user)


def staff_has_resource(user, *keys: str) -> bool:
    """True si ``user`` a accès à AU MOINS une des ressources ``keys``."""
    if not (user and user.is_authenticated):
        return False
    granted = effective_resources(user)
    return any(k in granted for k in keys)
