"""Admin — fiche d'adhésion d'un membre (infos de la demande soumise).

L'endpoint expose ce que le demandeur a renseigné à la soumission (colonnes
Article 2 + champs dynamiques FormSchema `extra_payload` + pièces).
"""
from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps_coop.members.models import Document, MembershipRequest
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestMemberAdhesion:
    def test_renvoie_les_infos_de_la_demande(self):
        staff = _staff()
        member = MemberFactory()
        MembershipRequest.objects.create(
            member=member,
            nom="Mballa",
            prenom="Jean",
            email="jean@t.local",
            phone="699112233",
            whatsapp="699112233",
            city="Douala",
            quartier_localite="Akwa",
            statut_pro=MembershipRequest.StatutPro.COMMERCANT,
            urgence_nom="Marie",
            urgence_lien="Épouse",
            urgence_phone="690000000",
            motivation="Épargner pour mon commerce.",
            extra_payload={"carte_cga": "CGA-42", "revenu_mensuel": "150000"},
            form_schema_version=3,
            statut=MembershipRequest.Statut.APPROUVEE,
        )

        r = _api(staff.user).get(f"/api/v1/admin/members/{member.id}/adhesion/")
        assert r.status_code == 200
        assert r.data["identity"]["nom"] == "Mballa"
        assert r.data["identity"]["email"] == "jean@t.local"
        assert r.data["identity"]["statut_pro"] == "Commerçant"
        assert r.data["urgence"]["nom"] == "Marie"
        assert r.data["motivation"] == "Épargner pour mon commerce."
        assert r.data["extra_payload"]["carte_cga"] == "CGA-42"
        assert r.data["form_schema_version"] == 3

    def test_membre_sans_demande_liee_fallback(self):
        """Membre sans MembershipRequest → fiche MINIMALE (données membre),
        plus de 404 « n'existe pas »."""
        staff = _staff()
        member = MemberFactory(nom="SANSREQ")  # créé sans MembershipRequest
        r = _api(staff.user).get(f"/api/v1/admin/members/{member.id}/adhesion/")
        assert r.status_code == 200
        assert r.data["identity"]["nom"] == "SANSREQ"
        assert r.data["source"] == "membre"

    def _make_doc(self, member, field_id):
        return Document.objects.create(
            member=member,
            type_doc=Document.TypeDoc.AUTRE,
            entite_liee_type="Member",
            entite_liee_id=member.id,
            fichier=SimpleUploadedFile(f"{field_id}.png", b"x", content_type="image/png"),
            schema_field_id=field_id,
        )

    def test_pieces_fallback_sur_documents_membre_cree_manuellement(self, tmp_path, settings):
        """Membre créé manuellement : sa demande liée a des champs pièces VIDES,
        mais les pièces chargées à la définition du mot de passe (Document) doivent
        remonter dans la fiche « Voir plus »."""
        settings.MEDIA_ROOT = str(tmp_path)
        staff = _staff()
        member = MemberFactory()
        MembershipRequest.objects.create(
            member=member,
            nom="Manu",
            prenom="Elle",
            email="manu@t.local",
            phone="699",
            statut=MembershipRequest.Statut.APPROUVEE,
            extra_payload={"cree_manuellement": True},
        )
        self._make_doc(member, "cni")
        self._make_doc(member, "photo")
        self._make_doc(member, "plan")

        r = _api(staff.user).get(f"/api/v1/admin/members/{member.id}/adhesion/")
        assert r.status_code == 200
        assert r.data["pieces"]["cni_recto"], "CNI (Document) doit remonter"
        assert r.data["pieces"]["photo_identite"], "photo (Document) doit remonter"
        assert r.data["pieces"]["plan_localisation"], "plan (Document) doit remonter"

    def test_pieces_fallback_sur_documents_sans_demande_liee(self, tmp_path, settings):
        """Branche fiche minimale (pas de MembershipRequest) : les Document doivent
        aussi remonter."""
        settings.MEDIA_ROOT = str(tmp_path)
        staff = _staff()
        member = MemberFactory(nom="SANSREQ")
        self._make_doc(member, "cni")

        r = _api(staff.user).get(f"/api/v1/admin/members/{member.id}/adhesion/")
        assert r.status_code == 200
        assert r.data["source"] == "membre"
        assert r.data["pieces"]["cni_recto"], "CNI (Document) doit remonter"

    def test_non_staff_refuse(self):
        member = MemberFactory()
        r = _api(member.user).get(f"/api/v1/admin/members/{member.id}/adhesion/")
        assert r.status_code in (401, 403)
