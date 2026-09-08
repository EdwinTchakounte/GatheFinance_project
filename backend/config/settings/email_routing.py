"""Choix de la voie e-mail — volontairement SANS aucun import Django.

Pourquoi un module à part : la règle « quand le repli SMTP s'interpose-t-il ? »
doit être vérifiable par un test, or la tester en chargeant ``settings.prod``
obligeait à installer les dépendances de PRODUCTION (whitenoise…) que la CI
n'installe pas — le test passait en local et cassait en CI. Isolée ici, la
règle se teste par un appel de fonction, dans n'importe quel environnement.
"""
from __future__ import annotations

#: Backend à double voie (cf. ``apps_coop.notifications.email_backends``).
FAILOVER_BACKEND = "apps_coop.notifications.email_backends.FailoverEmailBackend"

#: Backends de « test à blanc » : on veut lire l'e-mail dans les logs, pas
#: déclencher un repli SMTP. Ne jamais les envelopper.
_DRY_RUN_MARKERS = ("console", "locmem", "dummy")


def resolve_email_backends(requested: str, *, fallback_backend: str) -> tuple[str, str]:
    """Renvoie ``(EMAIL_BACKEND, EMAIL_PRIMARY_BACKEND)``.

    ``requested`` : ce que demande l'environnement (Brevo par défaut).
    ``fallback_backend`` : chemin du SMTP de secours, vide si non configuré.

    Sans secours configuré, on rend le backend demandé tel quel — comportement
    strictement identique à celui d'avant l'ajout du repli.
    """
    requested = (requested or "").strip()
    if fallback_backend and not any(m in requested for m in _DRY_RUN_MARKERS):
        return FAILOVER_BACKEND, requested
    return requested, requested
