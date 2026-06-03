"""LOT 1 (refonte 2026) — Identifiant configurable + statut BRC.

Couvre :
  - ``generate_numero_membre`` lit ``member.id.format`` (AppSetting)
    et incrémente correctement la séquence annuelle
  - Property ``Member.seniority_months`` (calcul mois écoulés)
  - Property ``Member.is_senior`` (seuil tunable via AppSetting)
  - Services BRC : upload, validation, rejet, idempotence, motif obligatoire
  - Cas multi-uploads (rejet → re-upload OK)
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.members.models import BRCDocument, Member
from apps_coop.members.services import (
    generate_numero_membre,
    reject_brc_document,
    upload_brc_document,
    validate_brc_document,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _override_media_root(tmp_path, settings):
    """Tests d'upload BRC : isole MEDIA_ROOT dans un dossier tmp.

    Le ``media/`` du repo est parfois owned-by-root (résidu Docker) et
    refuse l'écriture. On force MEDIA_ROOT en tmp_path pour que
    ``FileField.upload_to`` ait toujours un dossier writable.
    """
    settings.MEDIA_ROOT = str(tmp_path)


# ---------------------------------------------------------------------------
# Identifiant membre — format configurable
# ---------------------------------------------------------------------------


class TestGenerateNumeroMembre:
    """Le générateur lit ``member.id.format`` et calcule la prochaine séquence."""

    def test_default_format_and_uniqueness(self, active_member):
        """Vérifie le format par défaut + l'unicité (max+1)."""
        year = date.today().year
        existing_numeros = set(
            Member.objects.filter(
                numero_membre__startswith=f"GF-{year}-"
            ).values_list("numero_membre", flat=True)
        )
        n = generate_numero_membre()
        assert n.startswith(f"GF-{year}-")
        suffix = n.split("-")[-1]
        assert len(suffix) == 4
        assert suffix.isdigit()
        # Le nouveau numéro doit être strictement supérieur à tous les existants.
        if existing_numeros:
            max_existing = max(int(num.split("-")[-1]) for num in existing_numeros)
            assert int(suffix) == max_existing + 1

    def test_custom_format_via_appsetting(self, active_member):
        """L'admin change le format → le générateur l'applique."""
        AppSetting.objects.update_or_create(
            cle="member.id.format",
            defaults={"valeur": "COOP-{year}-{seq:06d}"},
        )
        year = date.today().year
        n = generate_numero_membre()
        assert n.startswith(f"COOP-{year}-")
        # Suffixe 6 chiffres.
        suffix = n.split("-")[-1]
        assert len(suffix) == 6

    def test_malformed_format_falls_back_to_default(self, active_member):
        """Format cassé → fallback silencieux sur GF-{year}-{seq:04d}."""
        AppSetting.objects.update_or_create(
            cle="member.id.format",
            defaults={"valeur": "BROKEN-NO-PLACEHOLDERS"},
        )
        year = date.today().year
        n = generate_numero_membre()
        # Ne doit JAMAIS planter, on retombe sur défaut.
        assert n.startswith(f"GF-{year}-")

    def test_sequence_picks_max_then_plus_one(self, active_member):
        """Si des numéros existants ont des séquences éparpillées, on prend max+1."""
        year = date.today().year
        # On crée des numéros manuellement avec une séquence haute.
        User = get_user_model()
        for i, seq in enumerate([42, 7, 99], start=1):
            user = User.objects.create_user(
                username=f"seqtest{i}@x.fr", email=f"seqtest{i}@x.fr"
            )
            Member.objects.create(
                user=user,
                numero_membre=f"GF-{year}-{seq:04d}",
                nom="X",
                prenom="Y",
                date_adhesion=date.today(),
            )
        n = generate_numero_membre()
        assert n == f"GF-{year}-0100"  # max 99 + 1


# ---------------------------------------------------------------------------
# Properties — seniority_months + is_senior
# ---------------------------------------------------------------------------


class TestSeniorityProperties:

    def test_seniority_zero_when_just_joined(self, active_member):
        active_member.date_adhesion = date.today()
        active_member.save(update_fields=["date_adhesion"])
        assert active_member.seniority_months == 0
        assert active_member.is_senior is False

    def test_seniority_12_months(self, active_member):
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])
        # ~13 mois écoulés → senior.
        assert active_member.seniority_months >= 12
        assert active_member.is_senior is True

    def test_is_senior_threshold_configurable(self, active_member):
        """Le seuil peut être abaissé par l'admin via AppSetting."""
        active_member.date_adhesion = date.today() - timedelta(days=180)  # ~6 mois
        active_member.save(update_fields=["date_adhesion"])
        # Seuil par défaut 12 mois → pas senior.
        assert active_member.is_senior is False

        # Admin abaisse le seuil à 3 mois.
        AppSetting.objects.update_or_create(
            cle="seniority.threshold_months", defaults={"valeur": "3"}
        )
        assert active_member.is_senior is True

    def test_seniority_no_adhesion_returns_zero(self, active_member):
        # Cas pathologique : date_adhesion vide en mémoire (le champ DB est
        # NOT NULL, donc on ne sauvegarde pas — on teste juste le garde-fou
        # côté property).
        active_member.date_adhesion = None
        assert active_member.seniority_months == 0
        assert active_member.is_senior is False


# ---------------------------------------------------------------------------
# Services BRC
# ---------------------------------------------------------------------------


def _make_pdf_file(name="brc.pdf", content=b"PDF-FAKE-CONTENT") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class TestUploadBRCDocument:

    def test_upload_creates_doc_en_attente(self, active_member, admin_user):
        fichier = _make_pdf_file("attestation_brc.pdf")
        doc = upload_brc_document(
            member=active_member,
            fichier=fichier,
            nom_original="attestation_brc.pdf",
            taille=fichier.size,
        )
        assert doc.id is not None
        assert doc.statut == BRCDocument.Statut.EN_ATTENTE
        assert doc.member == active_member
        assert doc.nom_original == "attestation_brc.pdf"
        assert doc.taille > 0

    def test_upload_writes_audit(self, active_member):
        upload_brc_document(
            member=active_member,
            fichier=_make_pdf_file(),
            nom_original="x.pdf",
            taille=100,
        )
        audit = AuditLog.objects.filter(
            action="member.brc_document_uploaded"
        ).first()
        assert audit is not None
        assert audit.details_json["numero_membre"] == active_member.numero_membre


class TestValidateBRCDocument:

    def test_validation_flips_member_flag(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        # Avant validation.
        assert active_member.is_brc_member is False

        validate_brc_document(doc=doc, validated_by=admin_user)

        doc.refresh_from_db()
        active_member.refresh_from_db()
        assert doc.statut == BRCDocument.Statut.VALIDE
        assert doc.validated_by == admin_user
        assert doc.validated_at is not None
        assert active_member.is_brc_member is True
        assert active_member.brc_validated_at is not None
        assert active_member.brc_validated_by == admin_user

    def test_validation_idempotent(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        validate_brc_document(doc=doc, validated_by=admin_user)
        first_validation_at = doc.validated_at

        # 2ᵉ appel — pas de re-validation.
        validate_brc_document(doc=doc, validated_by=admin_user)
        doc.refresh_from_db()
        assert doc.validated_at == first_validation_at

    def test_cannot_validate_rejected_document(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        reject_brc_document(doc=doc, rejected_by=admin_user, motif="Doc illisible")

        with pytest.raises(ValueError, match="rejeté"):
            validate_brc_document(doc=doc, validated_by=admin_user)


class TestRejectBRCDocument:

    def test_reject_writes_motif_and_status(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        reject_brc_document(
            doc=doc, rejected_by=admin_user, motif="Document non lisible"
        )
        doc.refresh_from_db()
        assert doc.statut == BRCDocument.Statut.REJETE
        assert doc.motif_rejet == "Document non lisible"
        assert doc.validated_by == admin_user
        # Le flag membre N'est PAS posé.
        active_member.refresh_from_db()
        assert active_member.is_brc_member is False

    def test_reject_requires_motif(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        with pytest.raises(ValueError, match="motif"):
            reject_brc_document(doc=doc, rejected_by=admin_user, motif="")
        with pytest.raises(ValueError, match="motif"):
            reject_brc_document(doc=doc, rejected_by=admin_user, motif="   ")

    def test_cannot_reject_validated_document(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        validate_brc_document(doc=doc, validated_by=admin_user)

        with pytest.raises(ValueError, match="validé"):
            reject_brc_document(doc=doc, rejected_by=admin_user, motif="trop tard")

    def test_reject_idempotent(self, active_member, admin_user):
        doc = upload_brc_document(
            member=active_member, fichier=_make_pdf_file(),
            nom_original="x.pdf", taille=100,
        )
        reject_brc_document(doc=doc, rejected_by=admin_user, motif="raison 1")
        first_motif = doc.motif_rejet
        first_at = doc.validated_at

        # 2ᵉ appel — no-op (le motif initial ne change pas).
        reject_brc_document(doc=doc, rejected_by=admin_user, motif="raison 2")
        doc.refresh_from_db()
        assert doc.motif_rejet == first_motif
        assert doc.validated_at == first_at


# ---------------------------------------------------------------------------
# Flow complet — rejet puis re-upload puis validation
# ---------------------------------------------------------------------------


class TestMultiUploadCycle:
    """Le membre peut re-uploader après un rejet jusqu'à être validé."""

    def test_rejected_then_new_upload_then_validated(self, active_member, admin_user):
        doc1 = upload_brc_document(
            member=active_member, fichier=_make_pdf_file("v1.pdf"),
            nom_original="v1.pdf", taille=100,
        )
        reject_brc_document(doc=doc1, rejected_by=admin_user, motif="trop flou")

        # Membre re-upload.
        doc2 = upload_brc_document(
            member=active_member, fichier=_make_pdf_file("v2.pdf"),
            nom_original="v2.pdf", taille=200,
        )
        assert doc2.statut == BRCDocument.Statut.EN_ATTENTE

        # Admin valide la 2ᵉ version.
        validate_brc_document(doc=doc2, validated_by=admin_user)
        active_member.refresh_from_db()
        assert active_member.is_brc_member is True

        # On a bien 2 lignes en historique (1 rejeté + 1 validé).
        docs = BRCDocument.objects.filter(member=active_member).order_by("created_at")
        assert docs.count() == 2
        assert docs[0].statut == BRCDocument.Statut.REJETE
        assert docs[1].statut == BRCDocument.Statut.VALIDE
