"""Admin — renvoyer l'e-mail de création de compte (lien « définir mon mot de passe »).

Contexte (incident 2026-09) : huit jours d'envois en échec ont laissé des membres
approuvés sans leur lien, donc incapables de se connecter. Le rattrapage se
faisait par un shell Django sur le serveur ; c'est désormais un geste admin.

Ce que ces tests figent :
  - un renvoi émet un token NEUF et invalide le précédent (un lien expiré ne
    doit jamais être réexpédié tel quel) ;
  - l'issue réelle de l'envoi est rapportée, pas maquillée en succès ;
  - l'adresse peut être corrigée pour ce renvoi sans toucher à la fiche ;
  - l'accès est bien gouverné par la ressource RBAC « members ».
"""
from __future__ import annotations

from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.members.models import PasswordSetupToken
from apps_coop.members.services import ResendWelcomeError, resend_welcome_email
from apps_coop.notifications.models import EmailLog, EmailTemplate
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _url(member) -> str:
    return f"/api/v1/admin/members/{member.pk}/resend-welcome/"


def _superuser():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def welcome_template(db):
    """Template réel requis : sans lui, l'événement ne produit aucun EmailLog."""
    return EmailTemplate.objects.update_or_create(
        code="member.welcome",
        defaults={
            "objet": "Bienvenue {{ prenom }}",
            "corps_html": "<p>Lien : {{ password_setup_url }}</p>",
            "corps_texte": "Lien : {{ password_setup_url }}",
            "actif": True,
        },
    )[0]


# --- Le cœur : un token NEUF ------------------------------------------------


class TestTokenRegenere:
    def test_emet_un_nouveau_token_et_invalide_le_precedent(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        # Token d'origine, comme après l'approbation.
        ancien = PasswordSetupToken.objects.create(
            user=member.user,
            token="ancien-token-expire",
            expires_at=timezone.now() - timezone.timedelta(hours=1),
        )

        resend_welcome_email(member)

        ancien.refresh_from_db()
        assert ancien.used_at is not None, "l'ancien lien doit être invalidé"

        neuf = (
            PasswordSetupToken.objects.filter(user=member.user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        assert neuf is not None and neuf.pk != ancien.pk
        assert not neuf.is_expired
        # 72 h de validité (cf. PASSWORD_SETUP_TOKEN_TTL_HOURS).
        assert 71 <= (neuf.expires_at - timezone.now()).total_seconds() / 3600 <= 72

    def test_un_seul_token_actif_apres_plusieurs_renvois(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        for _ in range(3):
            resend_welcome_email(member)

        actifs = PasswordSetupToken.objects.filter(user=member.user, used_at__isnull=True)
        assert actifs.count() == 1


# --- L'issue réelle est rapportée -------------------------------------------


class TestIssueRapportee:
    def test_succes_rapporte_sent_true_et_trace_un_emaillog(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        res = resend_welcome_email(member)

        assert res["sent"] is True
        assert res["to"] == "membre@test.local"
        assert res["statut"] == EmailLog.Statut.ENVOYE
        assert EmailLog.objects.filter(
            template_id="member.welcome", destinataire="membre@test.local"
        ).exists()

    def test_echec_denvoi_rapporte_sent_false_avec_le_motif(self, welcome_template):
        """Un envoi qui casse ne doit PAS ressortir en succès — c'est ce
        maquillage qui a laissé courir la panne huit jours."""
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        with mock.patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=RuntimeError("Brevo 401 Key not found"),
        ):
            res = resend_welcome_email(member)

        assert res["sent"] is False
        assert res["statut"] == EmailLog.Statut.ECHEC
        assert "Key not found" in res["erreur"]

    def test_template_desactive_ne_ment_pas_sur_le_resultat(self, welcome_template):
        """Kill-switch admin : aucun EmailLog n'est écrit → on le dit."""
        welcome_template.actif = False
        welcome_template.save(update_fields=["actif"])

        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        res = resend_welcome_email(member)

        assert res["sent"] is False
        assert res["statut"] == "aucune_trace"


# --- Adresse de destination -------------------------------------------------


class TestAdresse:
    def test_to_email_corrige_la_destination_sans_toucher_la_fiche(self, welcome_template):
        member = MemberFactory()
        member.user.email = "faute-de-frappe@test.local"
        member.user.save(update_fields=["email"])

        res = resend_welcome_email(member, to_email="bonne.adresse@test.local")

        assert res["to"] == "bonne.adresse@test.local"
        member.user.refresh_from_db()
        assert member.user.email == "faute-de-frappe@test.local", "la fiche ne bouge pas"

    def test_sans_aucune_adresse_leve_une_erreur_explicite(self, welcome_template):
        member = MemberFactory()
        member.user.email = ""
        member.user.save(update_fields=["email"])

        with pytest.raises(ResendWelcomeError, match="Aucune adresse"):
            resend_welcome_email(member)

    def test_signale_que_le_membre_a_deja_un_mot_de_passe(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.set_password("un-mot-de-passe-solide")
        member.user.save(update_fields=["email", "password"])

        assert resend_welcome_email(member)["had_password"] is True


# --- Traçabilité ------------------------------------------------------------


def test_ecrit_un_audit_avec_lacteur(welcome_template):
    member = MemberFactory()
    member.user.email = "membre@test.local"
    member.user.save(update_fields=["email"])
    acteur = _superuser()

    resend_welcome_email(member, actor=acteur)

    log = AuditLog.objects.filter(action="member.welcome_resent").order_by("-id").first()
    assert log is not None
    assert log.entite_id == member.id
    assert log.details_json["destinataire"] == "membre@test.local"
    assert log.details_json["sent"] is True


# --- Endpoint + RBAC --------------------------------------------------------


class TestEndpoint:
    def test_superuser_peut_renvoyer(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        res = _api(_superuser()).post(_url(member), {}, format="json")

        assert res.status_code == 200
        assert res.json()["sent"] is True

    def test_accepte_une_adresse_de_substitution(self, welcome_template):
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        res = _api(_superuser()).post(
            _url(member), {"to_email": "autre@test.local"}, format="json"
        )

        assert res.status_code == 200
        assert res.json()["to"] == "autre@test.local"

    def test_membre_sans_adresse_renvoie_400_pas_500(self, welcome_template):
        member = MemberFactory()
        member.user.email = ""
        member.user.save(update_fields=["email"])

        res = _api(_superuser()).post(_url(member), {}, format="json")

        assert res.status_code == 400
        assert "adresse" in res.json()["detail"].lower()

    def test_membre_inexistant_renvoie_404(self, welcome_template):
        res = _api(_superuser()).post("/api/v1/admin/members/999999/resend-welcome/", {}, format="json")
        assert res.status_code == 404

    def test_membre_simple_interdit(self, welcome_template):
        cible = MemberFactory()
        intrus = MemberFactory()

        res = _api(intrus.user).post(_url(cible), {}, format="json")

        assert res.status_code in (401, 403)

    def test_anonyme_interdit(self, welcome_template):
        member = MemberFactory()
        assert APIClient().post(_url(member), {}, format="json").status_code in (401, 403)


# --- Lien expiré : quelle sortie proposer au membre ? -----------------------
#
# Un lien mort laissait le membre dans un cul-de-sac (« contacte l'agence »,
# et un bouton connexion inutile puisqu'il n'a pas de mot de passe). Le portail
# lui propose desormais « mot de passe oublie » — le code OTP fonctionne pour
# un compte sans mot de passe.
#
# MAIS pas pour tout le monde : `confirm_password_setup` est le SEUL flux qui
# collecte les pieces d'identite (CNI, photo, plan) des membres crees par
# l'admin. Y renoncer donnerait un acces sans dossier KYC. Le 410 porte donc
# `pieces_required`, qui pilote la sortie proposee.

VERIFY_URL = "/api/v1/auth/setup-password/verify/"


def _token_expire(member):
    from datetime import timedelta

    return PasswordSetupToken.objects.create(
        user=member.user,
        token=f"expire-{member.pk}",
        expires_at=timezone.now() - timedelta(hours=1),
    )


class TestLienExpire:
    def test_lien_expire_renvoie_410(self):
        member = MemberFactory()
        token = _token_expire(member)

        res = APIClient().get(VERIFY_URL, {"token": token.token})

        assert res.status_code == 410

    def test_sans_pieces_dues_le_libre_service_est_autorise(self):
        member = MemberFactory()
        member.pieces_a_fournir = False
        member.save(update_fields=["pieces_a_fournir"])
        token = _token_expire(member)

        res = APIClient().get(VERIFY_URL, {"token": token.token})

        assert res.status_code == 410
        assert res.json()["pieces_required"] is False

    def test_avec_pieces_dues_le_libre_service_est_refuse(self):
        """Sinon le membre obtiendrait un acces sans jamais deposer sa CNI."""
        member = MemberFactory()
        member.pieces_a_fournir = True
        member.save(update_fields=["pieces_a_fournir"])
        token = _token_expire(member)

        res = APIClient().get(VERIFY_URL, {"token": token.token})

        assert res.status_code == 410
        assert res.json()["pieces_required"] is True

    def test_un_token_inconnu_ne_dit_rien(self):
        """404 sans indice : pas d'enumeration a partir d'un token invente."""
        res = APIClient().get(VERIFY_URL, {"token": "jamais-emis"})

        assert res.status_code == 404
        assert "pieces_required" not in res.json()

    def test_un_renvoi_admin_redonne_un_lien_valide(self, welcome_template):
        """Le parcours complet : lien mort -> renvoi -> lien exploitable."""
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])
        mort = _token_expire(member)
        assert APIClient().get(VERIFY_URL, {"token": mort.token}).status_code == 410

        resend_welcome_email(member)

        neuf = (
            PasswordSetupToken.objects.filter(user=member.user, used_at__isnull=True)
            .latest("id")
        )
        assert APIClient().get(VERIFY_URL, {"token": neuf.token}).status_code == 200
        # L'ancien reste mort : un lien remis en circulation serait une faille.
        assert APIClient().get(VERIFY_URL, {"token": mort.token}).status_code == 410
