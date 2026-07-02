"""Mot de passe oublie (flow OTP) — tests des endpoints DRF.

Couvre :
  1. ``POST /auth/password-reset/request/`` : reponse opaque (anti-enumeration)
     pour un e-mail inconnu, sans creer de code ; cree un ``PasswordResetCode``
     pour un e-mail existant et envoie l'e-mail (EmailLog).
  2. ``POST /auth/password-reset/confirm/`` : happy path (code valide → nouveau
     mot de passe utilisable pour /auth/login/), refus sur code errone
     (incrementation ``attempts``) et sur code expire.

Le code OTP est rendu deterministe via un patch de ``secrets.randbelow``.
Le cache est vide a chaque test pour ne pas cumuler le throttle 5/h/IP.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from apps_coop.members.auth_views import _hash_code
from apps_coop.members.models import PasswordResetCode
from apps_coop.notifications.models import EmailLog, EmailTemplate


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Evite l'accumulation du throttle auth-password-reset entre tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def member_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="reset-test@gathe.test",
        email="reset-test@gathe.test",
        password="ancien-mdp-1234",
        first_name="Awa",
    )


@pytest.fixture
def otp_template(db):
    return EmailTemplate.objects.create(
        code="auth.password_reset_otp",
        objet="Ton code : {code}",
        corps_html="<p>Bonjour {prenom}, code {code} (expire {ttl_minutes} min)</p>",
        corps_texte="Bonjour {prenom}, code {code} (expire {ttl_minutes} min)",
        actif=True,
    )


def _request_reset(client: Client, email: str):
    return client.post(
        "/api/v1/auth/password-reset/request/",
        data={"email": email},
        content_type="application/json",
    )


def _confirm_reset(client: Client, email: str, code: str, new_password: str):
    return client.post(
        "/api/v1/auth/password-reset/confirm/",
        data={"email": email, "code": code, "new_password": new_password},
        content_type="application/json",
    )


class TestRequest:
    def test_unknown_email_is_opaque_and_creates_no_code(self):
        c = Client()
        r = _request_reset(c, "inconnu@nowhere.test")
        assert r.status_code == 200
        assert "code a" in r.json()["detail"].lower() or r.json()["detail"]
        assert PasswordResetCode.objects.count() == 0

    def test_existing_email_creates_code_and_sends_email(self, member_user, otp_template):
        c = Client()
        with patch("secrets.randbelow", return_value=42):
            r = _request_reset(c, member_user.email)
        assert r.status_code == 200
        # Un code actif, hashe (jamais en clair), expirant ~15 min.
        codes = PasswordResetCode.objects.filter(user=member_user, used_at__isnull=True)
        assert codes.count() == 1
        reset = codes.first()
        assert reset.code_hash == _hash_code("000042")
        assert timedelta(minutes=14) < (reset.expires_at - timezone.now()) <= timedelta(minutes=15)
        # E-mail parti (template present → EmailLog).
        assert EmailLog.objects.filter(destinataire=member_user.email).exists()

    def test_new_request_invalidates_previous_codes(self, member_user):
        c = Client()
        with patch("secrets.randbelow", return_value=1):
            _request_reset(c, member_user.email)
        with patch("secrets.randbelow", return_value=2):
            _request_reset(c, member_user.email)
        active = PasswordResetCode.objects.filter(user=member_user, used_at__isnull=True)
        assert active.count() == 1
        assert active.first().code_hash == _hash_code("000002")


class TestConfirm:
    def test_happy_path_changes_password_and_login_works(self, member_user):
        c = Client()
        with patch("secrets.randbelow", return_value=123456):
            _request_reset(c, member_user.email)

        r = _confirm_reset(c, member_user.email, "123456", "NouveauMdp!2026")
        assert r.status_code == 200

        member_user.refresh_from_db()
        assert member_user.check_password("NouveauMdp!2026")

        # Le code est consomme.
        reset = PasswordResetCode.objects.get(user=member_user)
        assert reset.used_at is not None

        # Login effectif avec le nouveau mot de passe.
        login = Client()
        login.get("/api/v1/auth/csrf/")
        lr = login.post(
            "/api/v1/auth/login/",
            data={"email": member_user.email, "password": "NouveauMdp!2026"},
            content_type="application/json",
        )
        assert lr.status_code == 200

    def test_wrong_code_is_rejected_and_increments_attempts(self, member_user):
        c = Client()
        with patch("secrets.randbelow", return_value=111111):
            _request_reset(c, member_user.email)

        r = _confirm_reset(c, member_user.email, "999999", "NouveauMdp!2026")
        assert r.status_code == 400

        reset = PasswordResetCode.objects.get(user=member_user)
        assert reset.attempts == 1
        assert reset.used_at is None
        # Le mot de passe n'a pas change.
        member_user.refresh_from_db()
        assert member_user.check_password("ancien-mdp-1234")

    def test_expired_code_is_rejected(self, member_user):
        c = Client()
        with patch("secrets.randbelow", return_value=222222):
            _request_reset(c, member_user.email)
        # Force l'expiration.
        PasswordResetCode.objects.filter(user=member_user).update(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        r = _confirm_reset(c, member_user.email, "222222", "NouveauMdp!2026")
        assert r.status_code == 400
        member_user.refresh_from_db()
        assert member_user.check_password("ancien-mdp-1234")
