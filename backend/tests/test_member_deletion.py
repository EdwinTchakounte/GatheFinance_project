"""Suppression définitive d'un membre (cascade) — service + endpoint admin.

Couvre : cascade effective (membre + user + épargne + audit), permission IsAdmin
(403 pour un staff non-admin), et le garde-fou intégrité tiers (409 si le membre
est avaliste d'un crédit non clôturé d'un autre membre).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.members.deletion_services import (
    delete_member_cascade,
    third_party_engagements,
)
from apps_coop.members.models import Member
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount

from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _delete_url(member_id: int) -> str:
    return f"/api/v1/admin/members/{member_id}/delete/"


def test_cascade_removes_member_user_savings_and_audits(admin_user):
    member = MemberFactory()  # crée User + Member + SavingsAccount
    user_id = member.user_id
    member_id = member.id
    ClassicSavingsAccount.objects.create(member=member, date_ouverture=date.today())

    recap = delete_member_cascade(member, actor=admin_user, motif="doublon")

    assert recap["member_id"] == member_id
    assert not Member.objects.filter(id=member_id).exists()
    assert not get_user_model().objects.filter(id=user_id).exists()
    assert not SavingsAccount.objects.filter(member_id=member_id).exists()
    assert not ClassicSavingsAccount.objects.filter(member_id=member_id).exists()
    assert AuditLog.objects.filter(
        action="member.deleted", entite_id=member_id
    ).exists()


def test_endpoint_requires_admin_and_soft_deletes(staff_user, admin_user):
    """L'endpoint « suppression » = radiation (soft-delete), non destructive."""
    member = MemberFactory()
    url = _delete_url(member.id)

    # Staff non-admin → 403, le membre reste actif.
    r = _api(staff_user).delete(url, {"motif": "x"}, format="json")
    assert r.status_code == 403
    assert Member.objects.filter(id=member.id).exists()

    # Admin → 200, le membre SUBSISTE mais est radié + login désactivé.
    r = _api(admin_user).delete(url, {"motif": "erreur de saisie"}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["deleted"] is True
    assert r.json()["soft_deleted"] is True
    member.refresh_from_db()
    assert member.statut == Member.Statut.RADIE
    member.user.refresh_from_db()
    assert member.user.is_active is False  # login bloqué


def test_soft_delete_hides_from_list_and_restore(admin_user):
    member = MemberFactory()
    c = _api(admin_user)
    c.delete(_delete_url(member.id), {"motif": "doublon"}, format="json")

    # Masqué de la liste par défaut, visible via ?statut=radie.
    default_ids = [m["id"] for m in c.get("/api/v1/admin/members/").json()["results"]]
    assert member.id not in default_ids
    radie_ids = [
        m["id"] for m in c.get("/api/v1/admin/members/?statut=radie").json()["results"]
    ]
    assert member.id in radie_ids

    # Restauration : réactive + repasse en suspendu.
    rr = c.post(f"/api/v1/admin/members/{member.id}/restore/")
    assert rr.status_code == 200
    member.refresh_from_db()
    assert member.statut == Member.Statut.SUSPENDU
    member.user.refresh_from_db()
    assert member.user.is_active is True


def test_soft_delete_allowed_even_when_active_avaliste(admin_user):
    """La radiation ne détruit rien → plus de blocage 409 (les engagements
    tiers sont préservés)."""
    from apps_coop.loans.models import AvalisteConsent, LoanRequest

    borrower = MemberFactory()
    guarantor = MemberFactory()
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=Decimal("50000"),
        duree_mois=3,
        motif="test avaliste",
    )
    AvalisteConsent.objects.create(
        loan_request=lr, avaliste=guarantor, couverture_ratio=Decimal("1")
    )
    assert third_party_engagements(guarantor)

    r = _api(admin_user).delete(_delete_url(guarantor.id), {}, format="json")
    assert r.status_code == 200, r.content
    guarantor.refresh_from_db()
    assert guarantor.statut == Member.Statut.RADIE
    # L'engagement (consentement avaliste) est conservé.
    assert AvalisteConsent.objects.filter(avaliste=guarantor).exists()
