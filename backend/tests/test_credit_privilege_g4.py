"""G4 — privilège accordé par le comité à la validation (tracé).

Le découvert (part sur confiance) n'est plus accordé à l'éligibilité (plancher
30 % obligatoire) mais par le COMITÉ à la validation, via une coche manuelle
tracée (qui/quand/motif).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps_coop.audit.models import AuditLog
from apps_coop.loans.models import LoanRequest
from apps_coop.loans.services import approve_loan_request
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


def _comite():
    n = User.objects.count()
    u = User.objects.create_user(
        email=f"comite-g4-{n}@g.test", password="x", username=f"comite-g4-{n}"
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _lr(member, gele="20000"):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test G4 privilège",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
        montant_gele_demandeur=Decimal(gele),
    )


def _approve(lr, comite, **kw):
    return approve_loan_request(
        lr,
        decided_by=comite,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
        **kw,
    )


def test_privilege_stocke_et_trace():
    lr = _lr(MemberFactory())  # apport 20 % → découvert 80 %
    loan = _approve(
        lr, _comite(),
        privilege_accorde=True,
        privilege_motif="Ancien apprenant vérifié — historique propre",
    )
    loan.refresh_from_db()
    assert loan.privilege_accorde is True
    assert "Ancien apprenant" in loan.privilege_motif
    assert loan.montant_decouvert == Decimal("80000.00")
    # Tracé dans l'audit.
    log = AuditLog.objects.filter(action="loan.approved", entite_id=loan.id).first()
    assert log is not None
    assert log.details_json["privilege_accorde"] is True


def test_defaut_sans_privilege():
    lr = _lr(MemberFactory())
    loan = _approve(lr, _comite())
    loan.refresh_from_db()
    assert loan.privilege_accorde is False
    assert loan.privilege_motif == ""
