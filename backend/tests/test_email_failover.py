"""Envoi e-mail à double voie : Brevo (nominal) puis repli SMTP NHR.

Ce que ces tests figent :
  - tant qu'aucun secours n'est configuré, RIEN ne change (comportement
    historique : l'erreur remonte) ;
  - quand Brevo échoue, le message part par le SMTP de secours ;
  - le repli est décidé message par message (un lot partiellement en échec ne
    rejoue QUE les messages tombés) ;
  - l'expéditeur est réécrit si le SMTP de secours l'impose, sans muter
    durablement le message de l'appelant ;
  - la voie réellement utilisée est tracée dans ``EmailLog.transport``.
"""
from __future__ import annotations

import pytest
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.test import override_settings

from apps_coop.notifications.models import EmailLog, EmailTemplate
from apps_coop.notifications.services import send_template

FAILOVER = "apps_coop.notifications.email_backends.FailoverEmailBackend"
LOCMEM = "django.core.mail.backends.locmem.EmailBackend"
HERE = "tests.test_email_failover"


class BrevoDown(Exception):
    """Panne de la voie nominale (quota épuisé, clé révoquée, API KO)."""


class AlwaysFailingBackend(BaseEmailBackend):
    """Voie nominale systématiquement en erreur."""

    def send_messages(self, email_messages):
        raise BrevoDown("brevo indisponible")


class UnopenableBackend(BaseEmailBackend):
    """Voie nominale qui ne s'ouvre même pas (DNS/TLS KO)."""

    def open(self):
        raise BrevoDown("connexion impossible")

    def send_messages(self, email_messages):  # pragma: no cover — jamais atteint
        raise AssertionError("send_messages ne doit pas être appelé")


class SelectiveFailingBackend(BaseEmailBackend):
    """Échoue pour les destinataires contenant ``ko``, réussit pour les autres."""

    accepted: list = []

    def send_messages(self, email_messages):
        for msg in email_messages:
            if any("ko" in addr for addr in msg.to):
                raise BrevoDown(f"rejeté : {msg.to}")
            type(self).accepted.append(msg)
        return len(email_messages)


class SilentRefusalBackend(BaseEmailBackend):
    """Ne lève pas mais ne délivre rien (0 envoyé) — refus silencieux."""

    def send_messages(self, email_messages):
        return 0


@pytest.fixture(autouse=True)
def _reset_recorders():
    SelectiveFailingBackend.accepted = []
    yield
    SelectiveFailingBackend.accepted = []


def _msg(to="membre@test.local", subject="Sujet"):
    return EmailMultiAlternatives(
        subject=subject,
        body="corps",
        from_email="GATHE Finance <noreply@gathe-finance.com>",
        to=[to],
    )


# --- Pas de secours configuré : comportement strictement inchangé ------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND="",
)
def test_sans_secours_configure_lerreur_remonte():
    with pytest.raises(BrevoDown):
        _msg().send(fail_silently=False)


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND="",
)
def test_sans_secours_fail_silently_ne_leve_pas():
    assert _msg().send(fail_silently=True) == 0


# --- Voie nominale OK : le secours n'est jamais sollicité --------------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.SelectiveFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_brevo_ok_le_secours_reste_au_repos(mailoutbox):
    msg = _msg(to="ok@test.local")
    assert msg.send(fail_silently=False) == 1
    assert len(SelectiveFailingBackend.accepted) == 1
    assert mailoutbox == []  # rien n'est passé par le SMTP de secours
    assert msg.gathe_transport == "primary"


# --- Bascule sur le secours -------------------------------------------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
    EMAIL_FALLBACK_FROM="",
)
def test_brevo_ko_le_message_part_par_le_smtp_de_secours(mailoutbox):
    msg = _msg()
    assert msg.send(fail_silently=False) == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["membre@test.local"]
    assert msg.gathe_transport == "fallback"


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.UnopenableBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_brevo_injoignable_a_louverture_bascule_tout_le_lot(mailoutbox):
    from django.core.mail import get_connection

    lot = [_msg("a@test.local"), _msg("b@test.local")]
    assert get_connection(fail_silently=False).send_messages(lot) == 2
    assert [m.to[0] for m in mailoutbox] == ["a@test.local", "b@test.local"]
    assert all(m.gathe_transport == "fallback" for m in lot)


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.SilentRefusalBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_refus_silencieux_de_brevo_bascule_aussi(mailoutbox):
    assert _msg().send(fail_silently=False) == 1
    assert len(mailoutbox) == 1


# --- Granularité : le repli est décidé PAR MESSAGE ---------------------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.SelectiveFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_seul_le_message_en_echec_est_rejoue_en_secours(mailoutbox):
    from django.core.mail import get_connection

    ok_avant, ko, ok_apres = _msg("ok1@test.local"), _msg("ko@test.local"), _msg("ok2@test.local")
    conn = get_connection(fail_silently=False)

    assert conn.send_messages([ok_avant, ko, ok_apres]) == 3
    # Les deux « ok » sont passés par Brevo, le « ko » par le secours seulement.
    assert [m.to[0] for m in SelectiveFailingBackend.accepted] == ["ok1@test.local", "ok2@test.local"]
    assert [m.to[0] for m in mailoutbox] == ["ko@test.local"]
    assert ok_avant.gathe_transport == "primary"
    assert ko.gathe_transport == "fallback"
    assert ok_apres.gathe_transport == "primary"


# --- Expéditeur imposé par le SMTP de secours -------------------------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
    EMAIL_FALLBACK_FROM="NHR <no-reply@nhr.local>",
)
def test_le_secours_reecrit_lexpediteur_et_garde_la_reponse(mailoutbox):
    msg = _msg()
    origine = msg.from_email
    msg.send(fail_silently=False)

    envoye = mailoutbox[0]
    assert envoye.from_email == "NHR <no-reply@nhr.local>"
    assert envoye.reply_to == [origine]  # les réponses reviennent chez GATHE
    # Le message de l'appelant n'est pas laissé muté.
    assert msg.from_email == origine
    assert msg.reply_to == []


# --- Les deux voies KO ------------------------------------------------------


@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_OPTIONS={},
)
def test_les_deux_voies_ko_leve_lerreur():
    with pytest.raises(BrevoDown):
        _msg().send(fail_silently=False)


# --- Traçabilité dans EmailLog ---------------------------------------------


@pytest.fixture
def template(db):
    return EmailTemplate.objects.create(
        code="test.failover",
        objet="Test repli",
        corps_html="<p>Bonjour</p>",
        corps_texte="Bonjour",
        actif=True,
    )


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_send_template_trace_la_voie_de_secours(template, mailoutbox):
    log = send_template("test.failover", to="membre@test.local")

    assert log.statut == EmailLog.Statut.ENVOYE  # l'e-mail EST parti
    assert log.transport == EmailLog.Transport.FALLBACK
    assert len(mailoutbox) == 1


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.SelectiveFailingBackend",
    EMAIL_FALLBACK_BACKEND=LOCMEM,
    EMAIL_FALLBACK_OPTIONS={},
)
def test_send_template_trace_la_voie_nominale(template):
    log = send_template("test.failover", to="ok@test.local")

    assert log.statut == EmailLog.Statut.ENVOYE
    assert log.transport == EmailLog.Transport.PRIMARY


@pytest.mark.django_db
@override_settings(
    EMAIL_BACKEND=FAILOVER,
    EMAIL_PRIMARY_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_BACKEND=f"{HERE}.AlwaysFailingBackend",
    EMAIL_FALLBACK_OPTIONS={},
)
def test_send_template_les_deux_voies_ko_reste_en_echec(template):
    log = send_template("test.failover", to="membre@test.local")

    assert log.statut == EmailLog.Statut.ECHEC
    assert log.transport == ""
    assert "brevo indisponible" in log.erreur


# --- Câblage des réglages de PRODUCTION -------------------------------------
#
# Ces tests chargent réellement ``config.settings.prod`` dans un sous-processus,
# avec un environnement contrôlé. Ils gardent l'invariant qui évite de rejouer
# la panne de septembre : le backend de repli ne doit JAMAIS être imposé par le
# docker-compose (téléversé à chaque déploiement) mais décidé par le code, qui
# voyage avec l'image. Un compose nommant un module absent de l'image =
# ImportError à chaque envoi, donc tous les e-mails muets.


def _prod_setting(nom_reglage: str, **env_supplementaire) -> str:
    """Valeur d'un réglage tel que ``config.settings.prod`` le calcule."""
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "test-only",
        "DJANGO_ALLOWED_HOSTS": "example.com",
        "DEFAULT_FROM_EMAIL": "test@example.com",
        # Neutralise l'héritage du shell courant.
        "EMAIL_BACKEND": "",
        "EMAIL_FALLBACK_SMTP_HOST": "",
    }
    env.update({k: str(v) for k, v in env_supplementaire.items()})
    # Une valeur vide signifie « variable absente » côté déploiement.
    for cle in [k for k, v in env.items() if v == ""]:
        env.pop(cle)

    out = subprocess.run(
        [
            sys.executable, "-c",
            "import django;django.setup();"
            "from django.conf import settings;"
            f"print(getattr(settings, {nom_reglage!r}, ''))",
        ],
        capture_output=True, text=True, env=env, cwd=".",
    )
    assert out.returncode == 0, out.stderr[-800:]
    return out.stdout.strip()


class TestReglagesProduction:
    def test_sans_smtp_de_secours_le_module_de_repli_nest_pas_utilise(self):
        """Cas du déploiement standard : rien ne change par rapport à avant."""
        assert _prod_setting("EMAIL_BACKEND") == "anymail.backends.brevo.EmailBackend"

    def test_avec_smtp_de_secours_le_repli_sinterpose(self):
        assert _prod_setting(
            "EMAIL_BACKEND", EMAIL_FALLBACK_SMTP_HOST="smtp.exemple.test",
        ) == FAILOVER
        assert _prod_setting(
            "EMAIL_PRIMARY_BACKEND", EMAIL_FALLBACK_SMTP_HOST="smtp.exemple.test",
        ) == "anymail.backends.brevo.EmailBackend"

    def test_un_test_a_blanc_console_nest_jamais_enveloppe(self):
        """On veut lire l'e-mail dans les logs, pas déclencher un repli SMTP."""
        assert _prod_setting(
            "EMAIL_BACKEND",
            EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
            EMAIL_FALLBACK_SMTP_HOST="smtp.exemple.test",
        ) == "django.core.mail.backends.console.EmailBackend"

    def test_le_compose_de_production_ne_nomme_pas_le_module_de_repli(self):
        """Garde-fou d'infrastructure : `deploy.yml` téléverse ce fichier même
        quand il conserve l'ANCIENNE image (repli sur cache, rollback)."""
        from pathlib import Path

        compose = Path(__file__).resolve().parents[2] / "infra" / "docker-compose.prod.yml"
        contenu = compose.read_text(encoding="utf-8")
        lignes_actives = [
            ligne for ligne in contenu.splitlines()
            if "FailoverEmailBackend" in ligne and not ligne.strip().startswith("#")
        ]
        assert lignes_actives == [], (
            "docker-compose.prod.yml ne doit pas imposer le backend de repli : "
            "c'est config/settings/prod.py qui décide, car il voyage avec l'image."
        )
