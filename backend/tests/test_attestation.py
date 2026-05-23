"""Tests de l'attestation d'adhésion (PDF) et de sa jonction à l'e-mail
de bienvenue (UC1).

Couvre :
  - build_attestation_pdf : octets PDF valides, robuste aux champs vides
  - _fr_date : format FR lisible (1ᵉʳ pour le jour 1)
  - _send_welcome_email : l'attestation est bien jointe à l'e-mail envoyé
  - dégradé gracieux : si la génération PDF échoue, l'e-mail part quand même
"""
from __future__ import annotations

from datetime import date
from unittest import mock

import pytest
from django.core import mail

from apps_coop.members.attestation import _fr_date, build_attestation_pdf
from apps_coop.members.services import _send_welcome_email
from apps_coop.notifications.models import EmailTemplate
from apps_coop.payments.models import FeeType


pytestmark = pytest.mark.django_db


# -- Génération PDF ---------------------------------------------------------


class TestBuildAttestationPdf:
    def test_returns_valid_pdf_bytes(self, active_member):
        pdf = build_attestation_pdf(active_member)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b"%PDF-")
        assert pdf.rstrip().endswith(b"%%EOF")
        assert len(pdf) > 1000  # une vraie page, pas un stub vide

    def test_robust_when_optional_fields_blank(self, active_member):
        active_member.phone = ""
        # date_adhesion absente → fallback date.today(), pas d'exception
        active_member.date_adhesion = None
        pdf = build_attestation_pdf(active_member)
        assert pdf.startswith(b"%PDF-")


class TestFrDate:
    def test_first_day_uses_ordinal(self):
        assert _fr_date(date(2026, 1, 1)) == "1ᵉʳ janvier 2026"

    def test_regular_day(self):
        assert _fr_date(date(2026, 5, 23)) == "23 mai 2026"

    def test_all_months_have_a_name(self):
        for month in range(1, 13):
            assert _fr_date(date(2026, month, 15)).split()[1]


# -- Jonction à l'e-mail de bienvenue ---------------------------------------


@pytest.fixture
def welcome_template(db):
    return EmailTemplate.objects.create(
        code="member.welcome",
        objet="Bienvenue {prenom}",
        corps_html="<p>Bonjour {prenom} {nom} — n° {numero_membre}</p>",
        corps_texte="",
        actif=True,
    )


@pytest.fixture
def adhesion_fees(db):
    FeeType.objects.create(code=FeeType.Code.ADHESION, libelle="Adhésion", montant=10000)
    FeeType.objects.create(code=FeeType.Code.INSCRIPTION, libelle="Inscription", montant=2000)


class TestWelcomeEmailAttachment:
    def test_pdf_is_attached(self, active_member, welcome_template, adhesion_fees):
        _send_welcome_email(active_member, "awa@example.cm")

        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert msg.to == ["awa@example.cm"]
        assert len(msg.attachments) == 1
        filename, content, mimetype = msg.attachments[0]
        assert filename == "attestation_adhesion.pdf"
        assert mimetype == "application/pdf"
        assert content.startswith(b"%PDF-") if isinstance(content, bytes) else content.encode().startswith(b"%PDF-")

    def test_email_sent_without_attachment_if_pdf_fails(
        self, active_member, welcome_template, adhesion_fees
    ):
        with mock.patch(
            "apps_coop.members.attestation.build_attestation_pdf",
            side_effect=RuntimeError("boom"),
        ):
            _send_welcome_email(active_member, "awa@example.cm")

        # L'e-mail part quand même, sans pièce jointe.
        assert len(mail.outbox) == 1
        assert mail.outbox[0].attachments == []

    def test_no_email_when_recipient_missing(self, active_member, welcome_template):
        _send_welcome_email(active_member, "")
        assert mail.outbox == []
