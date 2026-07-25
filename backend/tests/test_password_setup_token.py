"""PWD Option B — Tests du flow de definition de mot de passe initial.

Couvre :
  1. Le service ``issue_password_setup_token`` cree un token unique, invalide
     les precedents non utilises (un seul actif par user).
  2. ``GET /auth/setup-password/verify/?token=...`` valide un token actif,
     refuse 410 sur token expire/utilise, 404 sur token inconnu.
  3. ``POST /auth/setup-password/confirm/`` pose le mot de passe + marque le
     token utilise + refuse toute reutilisation.
  4. Le mot de passe pose est utilisable pour /auth/login/.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps_coop.members.models import PasswordSetupToken
from apps_coop.members.services import issue_password_setup_token


pytestmark = pytest.mark.django_db


@pytest.fixture
def pending_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="setup-test@gathe.test",
        email="setup-test@gathe.test",
        password="random-unknown-1234",  # random tel que pose par approve_membership_request
    )


class TestServiceIssueToken:
    def test_creates_active_token_72h(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        assert token.token
        assert len(token.token) >= 32
        assert token.used_at is None
        assert not token.is_expired
        # TTL 72h +/- 1 min
        delta = token.expires_at - timezone.now()
        assert timedelta(hours=71, minutes=58) < delta <= timedelta(hours=72)

    def test_issuing_a_new_token_invalidates_previous_active(self, pending_user):
        old = issue_password_setup_token(user=pending_user)
        new = issue_password_setup_token(user=pending_user)
        old.refresh_from_db()
        assert old.used_at is not None  # invalide
        assert new.used_at is None
        # Et un seul actif en base
        active = PasswordSetupToken.objects.filter(user=pending_user, used_at__isnull=True)
        assert active.count() == 1
        assert active.first().pk == new.pk


class TestVerifyEndpoint:
    def test_valid_token_returns_email_mask(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        r = c.get(f"/api/v1/auth/setup-password/verify/?token={token.token}")
        assert r.status_code == 200
        body = r.json()
        assert body["email_mask"].startswith("s")
        assert "@gathe.test" in body["email_mask"]
        assert "expires_at" in body

    def test_unknown_token_returns_404(self):
        c = Client()
        r = c.get("/api/v1/auth/setup-password/verify/?token=nope-not-a-token")
        assert r.status_code == 404

    def test_expired_token_returns_410(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        token.expires_at = timezone.now() - timedelta(hours=1)
        token.save(update_fields=["expires_at"])
        c = Client()
        r = c.get(f"/api/v1/auth/setup-password/verify/?token={token.token}")
        assert r.status_code == 410

    def test_used_token_returns_410(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        token.used_at = timezone.now()
        token.save(update_fields=["used_at"])
        c = Client()
        r = c.get(f"/api/v1/auth/setup-password/verify/?token={token.token}")
        assert r.status_code == 410


class TestConfirmEndpoint:
    def test_sets_password_and_marks_token_used(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        c.get("/api/v1/auth/csrf/")
        r = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": "NewStrongPass!42"},
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["email"] == pending_user.email

        token.refresh_from_db()
        assert token.used_at is not None

        # Le nouveau mot de passe permet de se connecter.
        pending_user.refresh_from_db()
        assert pending_user.check_password("NewStrongPass!42")

    def test_reusing_a_consumed_token_returns_410(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        c.get("/api/v1/auth/csrf/")
        r1 = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": "FirstStrongPass!42"},
            content_type="application/json",
        )
        assert r1.status_code == 200

        r2 = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": "SecondStrongPass!42"},
            content_type="application/json",
        )
        assert r2.status_code == 410

    def test_short_password_now_accepted(self, pending_user):
        # 2026-07-24 : durcissement mot de passe RETIRÉ → un mot de passe court
        # ("abc") est désormais accepté (plus de validateurs de complexité).
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        c.get("/api/v1/auth/csrf/")
        r = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": "abc"},
            content_type="application/json",
        )
        assert r.status_code == 200
        token.refresh_from_db()
        assert token.used_at is not None

    def test_empty_password_returns_400(self, pending_user):
        # Le champ reste obligatoire : mot de passe vide → 400, token intact.
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        c.get("/api/v1/auth/csrf/")
        r = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": ""},
            content_type="application/json",
        )
        assert r.status_code == 400
        token.refresh_from_db()
        assert token.used_at is None

    def test_unknown_token_returns_404(self):
        c = Client()
        c.get("/api/v1/auth/csrf/")
        r = c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": "nope", "password": "StrongPass!42"},
            content_type="application/json",
        )
        assert r.status_code == 404


class TestLoginAfterSetup:
    def test_user_can_login_with_new_password(self, pending_user):
        token = issue_password_setup_token(user=pending_user)
        c = Client()
        c.get("/api/v1/auth/csrf/")
        c.post(
            "/api/v1/auth/setup-password/confirm/",
            data={"token": token.token, "password": "BrandNewPass!42"},
            content_type="application/json",
        )
        # Nouvelle session pour bien tester un vrai login.
        c2 = Client()
        c2.get("/api/v1/auth/csrf/")
        r = c2.post(
            "/api/v1/auth/login/",
            data={"email": pending_user.email, "password": "BrandNewPass!42"},
            content_type="application/json",
        )
        assert r.status_code == 200, r.content
