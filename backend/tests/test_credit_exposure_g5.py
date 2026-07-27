"""G5 — suivi : exposition globale de la coop au découvert (tableau de lecture)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.loans.models import LoanRequest
from apps_coop.loans.services import approve_loan_request
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db
User = get_user_model()

URL = "/api/v1/loans/admin/exposure/"


def _comite():
    n = User.objects.count()
    u = User.objects.create_user(
        email=f"comite-g5-{n}@g.test", password="x", username=f"comite-g5-{n}"
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _staff():
    n = User.objects.count()
    return User.objects.create_user(
        email=f"staff-g5-{n}@g.test", password="x", username=f"staff-g5-{n}",
        is_staff=True, is_superuser=True,
    )


def _approve(gele):
    lr = LoanRequest.objects.create(
        member=MemberFactory(),
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="G5",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
        montant_gele_demandeur=Decimal(gele),
    )
    return approve_loan_request(
        lr, decided_by=_comite(), taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )


def test_exposition_agrege_le_decouvert():
    _approve("20000")   # découvert 80 000
    _approve("100000")  # auto-couvert → découvert 0
    client = APIClient()
    client.force_authenticate(_staff())
    r = client.get(URL)
    assert r.status_code == 200, r.content
    data = r.json()
    assert Decimal(data["encours_decouvert_total"]) == Decimal("80000.00")
    assert data["nb_credits_actifs"] == 2


def test_paliers_alerte():
    AppSetting.objects.update_or_create(
        cle="loans.exposure.alert_step", defaults={"valeur": "50000"}
    )
    _approve("20000")  # découvert 80 000
    client = APIClient()
    client.force_authenticate(_staff())
    r = client.get(URL)
    data = r.json()
    # 80 000 / 50 000 = palier 1.
    assert data["alerte"]["palier_atteint"] == 1
    assert data["alerte"]["palier_step"] == "50000"


def test_non_staff_refuse():
    m = MemberFactory()
    client = APIClient()
    client.force_authenticate(m.user)
    assert client.get(URL).status_code == 403
