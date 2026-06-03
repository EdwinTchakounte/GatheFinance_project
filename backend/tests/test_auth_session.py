"""Audit session — vérifie le comportement bout en bout du cookie de session.

Couvre les flows :
  1. ``POST /auth/login/`` pose le cookie ``gathe_sessionid`` (HttpOnly, SameSite=Lax)
  2. ``GET /auth/me/`` renvoie le user tant que le cookie est envoyé (équivalent F5 navigateur)
  3. ``POST /auth/logout/`` invalide la session côté serveur
  4. Mauvais mot de passe → 401, pas de cookie posé
  5. Pas de cookie → /auth/me/ renvoie 403 IsAuthenticated
  6. Une nouvelle session après logout ne ré-utilise pas l'ancien sessionid

NB : on utilise ``django.test.Client`` qui propage automatiquement les cookies
entre requêtes, ce qui simule fidèlement un navigateur.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import Client


pytestmark = pytest.mark.django_db


@pytest.fixture
def member_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="session-test@gathe.test",
        email="session-test@gathe.test",
        password="test1234",
    )


@pytest.fixture
def staff_user(db):
    User = get_user_model()
    return User.objects.create_user(
        username="staff-session@gathe.test",
        email="staff-session@gathe.test",
        password="test1234",
        is_staff=True,
    )


def _login(c: Client, email: str, password: str):
    # Préparer le cookie CSRF d'abord (le SPA le fait au boot via /auth/csrf/).
    c.get("/api/v1/auth/csrf/")
    return c.post(
        "/api/v1/auth/login/",
        data={"email": email, "password": password},
        content_type="application/json",
    )


class TestLogin:
    def test_login_sets_session_cookie(self, member_user):
        c = Client()
        r = _login(c, member_user.email, "test1234")
        assert r.status_code == 200, r.content
        # Le cookie gathe_sessionid est posé.
        assert "gathe_sessionid" in c.cookies
        cookie = c.cookies["gathe_sessionid"]
        assert cookie.value != ""
        # HttpOnly attendu (sécurité).
        assert cookie["httponly"] is True

    def test_login_wrong_password_returns_401(self, member_user):
        c = Client()
        r = _login(c, member_user.email, "WRONG")
        assert r.status_code == 401
        # Pas de cookie de session posé (ou alors vide).
        cookie = c.cookies.get("gathe_sessionid")
        assert cookie is None or cookie.value == ""

    def test_login_returns_identity_payload(self, staff_user):
        c = Client()
        r = _login(c, staff_user.email, "test1234")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == staff_user.email
        assert body["is_staff"] is True

    def test_login_unknown_email_returns_401(self):
        c = Client()
        r = _login(c, "nobody@nowhere.test", "anything")
        assert r.status_code == 401


class TestSessionPersistence:
    """Reproduit le scénario F5 navigateur : login → me → me (≈ rafraîchissement)."""

    def test_me_works_immediately_after_login(self, member_user):
        c = Client()
        _login(c, member_user.email, "test1234")
        r = c.get("/api/v1/auth/me/")
        assert r.status_code == 200
        assert r.json()["email"] == member_user.email

    def test_me_persists_across_multiple_requests(self, member_user):
        """Simule plusieurs F5 : la session doit rester valide tant que le cookie est envoyé."""
        c = Client()
        _login(c, member_user.email, "test1234")
        for _ in range(5):
            r = c.get("/api/v1/auth/me/")
            assert r.status_code == 200, "Session a expiré trop tôt"

    def test_me_with_no_cookie_returns_403(self):
        c = Client()
        r = c.get("/api/v1/auth/me/")
        # IsAuthenticated → 403 (DRF) ou 401 selon config
        assert r.status_code in (401, 403)


class TestLogout:
    def test_logout_invalidates_session(self, member_user):
        c = Client()
        _login(c, member_user.email, "test1234")
        # Sanity : on est connecté
        assert c.get("/api/v1/auth/me/").status_code == 200

        # Logout
        r = c.post("/api/v1/auth/logout/")
        assert r.status_code in (200, 204)

        # Suite : /me doit maintenant échouer
        r2 = c.get("/api/v1/auth/me/")
        assert r2.status_code in (401, 403), "Logout n'a pas invalidé la session"

    def test_relogin_after_logout_creates_new_session(self, member_user):
        c = Client()
        _login(c, member_user.email, "test1234")
        sid1 = c.cookies["gathe_sessionid"].value

        c.post("/api/v1/auth/logout/")
        _login(c, member_user.email, "test1234")
        sid2 = c.cookies["gathe_sessionid"].value

        assert sid1 != sid2, "Le sessionid n'a pas été réémis après logout"


class TestSharedBackendBehavior:
    """Confirme que portail et admin partagent le MÊME cookie de session.

    C'est un comportement *intentionnel* du fait qu'ils utilisent le même
    backend Django avec le même nom de cookie (``gathe_sessionid``). Conséquence :
    se connecter sur l'admin écrase la session du portail dans le même
    navigateur (et inversement). Une vraie séparation nécessiterait deux
    backends ou des cookies nommés différemment.

    Ce test documente ce comportement plutôt que de le « corriger ».
    """

    def test_admin_login_replaces_member_session(self, member_user, staff_user):
        c = Client()
        # 1) Login member.
        _login(c, member_user.email, "test1234")
        body = c.get("/api/v1/auth/me/").json()
        assert body["email"] == member_user.email
        assert body["is_staff"] is False

        # 2) Login staff sur le même navigateur (même cookie jar) — sans logout préalable.
        _login(c, staff_user.email, "test1234")
        body = c.get("/api/v1/auth/me/").json()
        # La session a été remplacée → on est désormais staff.
        assert body["email"] == staff_user.email
        assert body["is_staff"] is True
