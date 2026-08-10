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


def test_endpoint_requires_admin(staff_user, admin_user):
    member = MemberFactory()
    url = _delete_url(member.id)

    # Staff non-admin → 403, le membre survit.
    r = _api(staff_user).delete(url, {"motif": "x"}, format="json")
    assert r.status_code == 403
    assert Member.objects.filter(id=member.id).exists()

    # Admin → 200, le membre disparaît.
    r = _api(admin_user).delete(url, {"motif": "erreur de saisie"}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["deleted"] is True
    assert not Member.objects.filter(id=member.id).exists()


def test_blocked_when_member_is_active_avaliste(admin_user):
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

    # Le helper signale l'engagement tiers…
    assert third_party_engagements(guarantor)

    # …et l'endpoint refuse la suppression (409), le membre survit.
    r = _api(admin_user).delete(_delete_url(guarantor.id), {}, format="json")
    assert r.status_code == 409, r.content
    assert Member.objects.filter(id=guarantor.id).exists()
