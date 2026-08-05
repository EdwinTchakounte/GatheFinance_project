"""Campagne = onboarding sans frais (2026).

Couvre :
  - Candidature publique visiteur refusée si ``membre_requis=True``.
  - Candidature publique acceptée (membre_requis=False, montant dans bornes) →
    ``CampaignApplication`` EN_ATTENTE, AUCUN compte créé à ce stade.
  - Montant hors bornes → 400.
  - Acceptation admin → crée le compte (statut ACTIF, microcampaign posé, SANS
    13K), SavingsAccount, PasswordSetupToken émis, LoanRequest EN_INSTRUCTION.
  - Rejet admin → aucun compte.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.models import (
    CampaignApplication,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.members.models import Member, PasswordSetupToken
from tests.factories import UserFactory


# transaction=True : les callbacks ``transaction.on_commit`` (émission du
# PasswordSetupToken + mail de bienvenue) ne s'exécutent qu'au commit réel.
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def comite_client(db):
    User = get_user_model()
    user = User.objects.create_user(
        username="comite@camp.local", email="comite@camp.local",
        password="x", is_staff=True,
    )
    g, _ = Group.objects.get_or_create(name="comite")
    user.groups.add(g)
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _campaign(*, membre_requis, frais=None, docs=None):
    today = date.today()
    return MicrocreditCampaign.objects.create(
        nom="Campagne visiteurs",
        profil_cible="commercants",
        date_debut=today - timedelta(days=2),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        membre_requis=membre_requis,
        frais_etude_montant=frais,
        documents_requis=docs or [],
        actif=True,
        created_by=UserFactory(),
    )


_APPLY = "/api/v1/loans/campaigns/{}/apply/"
_BODY = {
    "nom": "Doe", "prenom": "Jane", "phone": "237690000000",
    "email": "jane@visitor.cm", "montant": "20000", "motif": "Petit commerce",
}


class TestPublicApply:
    def test_rejected_when_membre_requis(self):
        camp = _campaign(membre_requis=True)
        resp = APIClient().post(_APPLY.format(camp.id), _BODY, format="json")
        assert resp.status_code == 400
        assert not CampaignApplication.objects.exists()

    def test_creates_application_no_account(self):
        camp = _campaign(membre_requis=False, frais=Decimal("0"))
        resp = APIClient().post(_APPLY.format(camp.id), _BODY, format="json")
        assert resp.status_code == 201, resp.content
        app = CampaignApplication.objects.get()
        assert app.statut == CampaignApplication.Statut.EN_ATTENTE
        assert app.member_id is None
        # Aucun compte créé à la candidature (anti-abus).
        assert not Member.objects.filter(nom="Doe").exists()

    def test_amount_out_of_bounds_rejected(self):
        camp = _campaign(membre_requis=False)
        body = {**_BODY, "montant": "999999"}
        resp = APIClient().post(_APPLY.format(camp.id), body, format="json")
        assert resp.status_code == 400

    def test_extra_payload_stored(self):
        """Les champs personnalisés (FormSchema) sont conservés sur la candidature."""
        camp = _campaign(membre_requis=False, frais=Decimal("0"))
        body = {
            **_BODY,
            "extra_payload": {"statut_pro": "independant", "annees_activite": 3},
            "form_schema_version": 2,
        }
        resp = APIClient().post(_APPLY.format(camp.id), body, format="json")
        assert resp.status_code == 201, resp.content
        app = CampaignApplication.objects.get()
        assert app.extra_payload == {"statut_pro": "independant", "annees_activite": 3}
        assert app.form_schema_version == 2

    def test_extra_payload_invalid_ignored(self):
        """Un extra_payload illisible ne fait jamais échouer la candidature."""
        camp = _campaign(membre_requis=False, frais=Decimal("0"))
        body = {**_BODY, "extra_payload": "not-a-dict"}
        resp = APIClient().post(_APPLY.format(camp.id), body, format="json")
        assert resp.status_code == 201, resp.content
        assert CampaignApplication.objects.get().extra_payload == {}


class TestAcceptOnboarding:
    def _apply(self):
        camp = _campaign(membre_requis=False, frais=Decimal("0"))
        APIClient().post(_APPLY.format(camp.id), _BODY, format="json")
        return camp, CampaignApplication.objects.get()

    def test_accept_creates_beneficiary_account(self, comite_client):
        camp, app = self._apply()
        url = f"/api/v1/loans/admin/campaign-applications/{app.id}/decide/"
        resp = comite_client.post(url, {"decision": "accepte"}, format="json")
        assert resp.status_code == 200, resp.content

        app.refresh_from_db()
        assert app.statut == CampaignApplication.Statut.ACCEPTEE
        member = app.member
        assert member is not None
        # Compte ACTIF (accès complet), origine campagne, SANS 13K.
        assert member.statut == Member.Statut.ACTIF
        assert member.microcampaign_id == camp.id
        # Mail de définition de mot de passe : token émis.
        assert PasswordSetupToken.objects.filter(user=member.user).exists()
        # Carnet obligatoire (règle 2026) : la demande reste EN_ATTENTE tant que
        # le carnet — facturé et réglé à la demande de crédit — n'est pas créé.
        from apps_coop.members.models import BookletOrder

        lr = app.loan_request
        assert lr is not None
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE
        assert not BookletOrder.objects.filter(member=member).exists()
        assert lr.microcampaign_id == camp.id
        assert Decimal(lr.montant_demande) == Decimal("20000")

    def test_reject_creates_no_account(self, comite_client):
        camp, app = self._apply()
        url = f"/api/v1/loans/admin/campaign-applications/{app.id}/decide/"
        resp = comite_client.post(
            url, {"decision": "rejete", "motif_rejet": "Profil hors cible"},
            format="json",
        )
        assert resp.status_code == 200, resp.content
        app.refresh_from_db()
        assert app.statut == CampaignApplication.Statut.REJETEE
        assert app.member_id is None


class TestDocumentsRequis:
    """Pièces justificatives exigées du candidat (onboarding 2026)."""

    def test_missing_document_rejected(self):
        camp = _campaign(
            membre_requis=False, frais=Decimal("0"),
            docs=["Preuve d'activité commerçant"],
        )
        # Candidature sans le fichier exigé → refus, aucune candidature créée.
        resp = APIClient().post(_APPLY.format(camp.id), _BODY, format="json")
        assert resp.status_code == 400, resp.content
        assert not CampaignApplication.objects.exists()

    def test_document_uploaded_creates_row(self, settings, tmp_path):
        from django.core.files.uploadedfile import SimpleUploadedFile

        settings.MEDIA_ROOT = str(tmp_path)
        camp = _campaign(
            membre_requis=False, frais=Decimal("0"),
            docs=["Preuve d'activité commerçant"],
        )
        proof = SimpleUploadedFile("preuve.pdf", b"%PDF-1.4 fake", content_type="application/pdf")
        resp = APIClient().post(
            _APPLY.format(camp.id),
            {**_BODY, "doc_0": proof},
            format="multipart",
        )
        assert resp.status_code == 201, resp.content
        app = CampaignApplication.objects.get()
        docs = list(app.documents.all())
        assert len(docs) == 1
        assert docs[0].label == "Preuve d'activité commerçant"
        assert docs[0].fichier
