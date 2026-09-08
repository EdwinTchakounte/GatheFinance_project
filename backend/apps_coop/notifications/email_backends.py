"""Backend e-mail à DOUBLE VOIE : Brevo (API HTTP) puis repli SMTP.

Pourquoi
--------
Les e-mails de la coopérative ne sont pas du marketing : « définir mon mot de
passe », « adhésion approuvée », « échéance J-3 », « saisie sur épargne ». Un
e-mail perdu bloque un membre. Or la voie nominale (API HTTP Brevo) peut tomber
pour des raisons qui n'ont rien à voir avec nous : quota mensuel épuisé, clé API
révoquée, compte suspendu pour réputation, API Brevo indisponible.

Ce backend rend donc l'envoi à **deux voies** :

1. **Voie nominale** — Brevo (``anymail.backends.brevo.EmailBackend``).
   Domaine authentifié (SPF/DKIM), bonne délivrabilité, arrive en boîte
   principale.
2. **Voie de secours** — SMTP NHR (``django.core.mail.backends.smtp``).
   Utilisée UNIQUEMENT si la voie 1 a échoué pour ce message. La délivrabilité
   y est dégradée (l'e-mail partira probablement en spam) : c'est **assumé**.
   Un e-mail en spam reste récupérable par le membre ; un e-mail jamais parti
   ne l'est pas.

Le repli est décidé **par message**, pas par lot : si 3 e-mails partent et que
seul le 2e échoue sur Brevo, seul le 2e est rejoué en SMTP.

Comment ça se branche
---------------------
Comme c'est un ``EMAIL_BACKEND`` Django standard, TOUT le code d'envoi existant
(``send_template``, les accusés de réception vitrine, l'alerte paiements
bloqués) en bénéficie sans une seule ligne modifiée : ils appellent
``msg.send()``, qui passe par ce backend.

Configuration (cf. ``config/settings/base.py``) :

- ``EMAIL_PRIMARY_BACKEND``  : chemin du backend nominal.
- ``EMAIL_FALLBACK_BACKEND`` : chemin du backend de secours. **Vide = pas de
  repli** → ce backend se comporte exactement comme le nominal (c'est le cas
  en dev et en CI : rien ne change).
- ``EMAIL_FALLBACK_OPTIONS`` : kwargs passés au backend de secours (host, port,
  username, password, use_tls…). Permet de viser le SMTP NHR sans polluer les
  réglages globaux ``EMAIL_HOST*`` (que le backend Brevo n'utilise pas).
- ``EMAIL_FALLBACK_FROM``    : expéditeur à substituer sur la voie de secours.
  La plupart des SMTP refusent un ``From:`` qu'ils n'ont pas autorisé (550
  "sender not allowed") — si le SMTP NHR n'accepte que ses propres adresses,
  renseigner cette variable. L'expéditeur d'origine est alors préservé en
  ``Reply-To`` pour que les réponses reviennent au bon endroit.

Observabilité
-------------
Chaque message envoyé est estampillé (``message.gathe_transport``) avec la voie
réellement utilisée : ``"primary"`` ou ``"fallback"``. ``send_template`` recopie
cette valeur dans ``EmailLog.transport``, ce qui rend le mode dégradé visible
dans l'écran Supervision (au lieu d'être silencieux).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

#: Valeurs posées sur ``message.gathe_transport`` et reprises par ``EmailLog``.
TRANSPORT_PRIMARY = "primary"
TRANSPORT_FALLBACK = "fallback"


class FailoverEmailBackend(BaseEmailBackend):
    """Essaie le backend nominal, puis le backend de secours message par message.

    Contrat Django respecté : ``send_messages`` renvoie le nombre de messages
    effectivement partis (par l'une OU l'autre voie) et ne lève que si
    ``fail_silently`` est faux ET que les deux voies ont échoué.
    """

    def __init__(self, fail_silently: bool = False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        # kwargs éventuels passés par get_connection() ; on les transmet au
        # backend nominal (le secours a sa propre config explicite).
        self._primary_kwargs = kwargs

    # -- Résolution des deux voies -------------------------------------------

    def _open_primary(self):
        """Connexion nominale, ou ``None`` si elle ne peut pas s'ouvrir."""
        path = getattr(settings, "EMAIL_PRIMARY_BACKEND", "") or ""
        if not path:
            return None
        try:
            conn = get_connection(backend=path, fail_silently=False, **self._primary_kwargs)
            conn.open()
            return conn
        except Exception:  # noqa: BLE001 — toute panne d'ouverture = on bascule
            logger.warning("Voie e-mail nominale (%s) indisponible à l'ouverture", path, exc_info=True)
            return None

    def _open_fallback(self):
        """Connexion de secours, ou ``None`` si non configurée / injoignable."""
        path = getattr(settings, "EMAIL_FALLBACK_BACKEND", "") or ""
        if not path:
            return None
        options = dict(getattr(settings, "EMAIL_FALLBACK_OPTIONS", {}) or {})
        try:
            conn = get_connection(backend=path, fail_silently=False, **options)
            conn.open()
            return conn
        except Exception:  # noqa: BLE001
            logger.exception("Voie e-mail de SECOURS (%s) indisponible à l'ouverture", path)
            return None

    # -- Envoi ----------------------------------------------------------------

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0

        sent = 0
        pending: list = []          # messages à rejouer en secours
        last_error: Exception | None = None

        primary = self._open_primary()
        if primary is None:
            pending = list(email_messages)
        else:
            try:
                for message in email_messages:
                    try:
                        delivered = primary.send_messages([message])
                    except Exception as exc:  # noqa: BLE001
                        last_error = exc
                        logger.warning(
                            "Envoi Brevo échoué pour %s (%s) — bascule sur le SMTP de secours",
                            getattr(message, "to", None),
                            exc,
                        )
                        pending.append(message)
                        continue
                    if delivered:
                        _stamp(message, TRANSPORT_PRIMARY)
                        sent += delivered
                    else:
                        # Refus sans exception (fail_silently interne au backend
                        # nominal, destinataire rejeté…) : on tente le secours.
                        logger.warning(
                            "Envoi Brevo refusé sans erreur pour %s — bascule sur le SMTP de secours",
                            getattr(message, "to", None),
                        )
                        pending.append(message)
            finally:
                try:
                    primary.close()
                except Exception:  # noqa: BLE001 — fermeture best-effort
                    logger.debug("Fermeture de la connexion nominale échouée", exc_info=True)

        if not pending:
            return sent

        fallback = self._open_fallback()
        if fallback is None:
            # Aucun secours disponible : on rend la main comme le ferait le
            # backend nominal seul (comportement historique).
            if last_error is not None and not self.fail_silently:
                raise last_error
            return sent

        try:
            for message in pending:
                original_from = message.from_email
                original_reply_to = list(message.reply_to or [])
                _apply_fallback_sender(message)
                try:
                    delivered = fallback.send_messages([message])
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    logger.exception(
                        "SMTP de secours échoué aussi pour %s — e-mail PERDU",
                        getattr(message, "to", None),
                    )
                    delivered = 0
                finally:
                    # On ne laisse pas l'appelant avec un message muté.
                    message.from_email = original_from
                    message.reply_to = original_reply_to
                if delivered:
                    _stamp(message, TRANSPORT_FALLBACK)
                    sent += delivered
                    logger.warning(
                        "E-mail délivré par la voie de SECOURS (spam probable) → %s",
                        getattr(message, "to", None),
                    )
        finally:
            try:
                fallback.close()
            except Exception:  # noqa: BLE001
                logger.debug("Fermeture de la connexion de secours échouée", exc_info=True)

        if sent < len(email_messages) and last_error is not None and not self.fail_silently:
            raise last_error
        return sent


# --- Helpers ----------------------------------------------------------------


def _stamp(message, transport: str) -> None:
    """Note sur le message la voie qui l'a réellement porté.

    ``msg.send()`` passe l'objet lui-même au backend : l'appelant
    (``send_template``) relit donc l'attribut juste après l'envoi.
    """
    try:
        message.gathe_transport = transport
    except Exception:  # noqa: BLE001 — un message exotique ne doit rien casser
        logger.debug("Impossible d'estampiller le transport sur le message", exc_info=True)


def _apply_fallback_sender(message) -> None:
    """Substitue l'expéditeur si le SMTP de secours impose le sien.

    Sans ça, un SMTP qui n'autorise que ses propres adresses rejette le message
    (550) et le repli ne sert à rien. L'expéditeur d'origine est conservé en
    ``Reply-To`` pour que les réponses des membres arrivent au bon endroit.
    """
    fallback_from = getattr(settings, "EMAIL_FALLBACK_FROM", "") or ""
    if not fallback_from or message.from_email == fallback_from:
        return
    original_from = message.from_email
    message.from_email = fallback_from
    if not message.reply_to and original_from:
        message.reply_to = [original_from]
