"""Régression — la vue admin d'encaissement des frais d'étude doit tourner
dans une transaction.

`_hook_loan_request_fees` fait un `select_for_update()`. Sans `ATOMIC_REQUESTS`,
une vue est en autocommit ; sous PostgreSQL (recette/prod) un `select_for_update`
en autocommit lève `TransactionManagementError` (500). SQLite l'ignore
silencieusement, donc un test « happy path » sur SQLite NE catche PAS le bug.

Ce test garde l'invariant réel, indépendamment du moteur : au moment où le hook
s'exécute, la connexion NE doit PAS être en autocommit (donc on est bien dans un
`transaction.atomic`). Il échoue si la vue perd son wrapper atomique.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from rest_framework.test import APIRequestFactory, force_authenticate

from apps_coop.audit.models import AppSetting
from apps_coop.loans.models import LoanRequest
from apps_coop.loans.views import loan_request_record_study_fee
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory


@pytest.mark.django_db(transaction=True)
def test_record_study_fee_runs_hook_inside_transaction(monkeypatch):
    """django_db(transaction=True) ⇒ pas de transaction ambiante de test :
    on observe le vrai mode de la vue (autocommit vs atomic)."""
    AppSetting.objects.update_or_create(
        cle="savings.placement.closed_from", defaults={"valeur": "2099-01-01"}
    )
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"montant": Decimal("5000"), "actif": True, "libelle": "frais"},
    )
    member = MemberFactory()
    ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal("31000"), date_ouverture=date(2026, 1, 1)
    )
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("50000"),
        duree_mois=2,
        motif="atomic-guard",
        statut=LoanRequest.Statut.EN_ATTENTE,
        montant_gele_demandeur=Decimal("10000"),
        cni_demandeur="123456789",
        moyen_reception="agence_especes",
    )

    # Espionne l'état autocommit au moment de l'appel du hook.
    import apps_coop.payments.services as pay_services

    seen = {}
    real_hook = pay_services._hook_loan_request_fees

    def _spy(payment, raw):
        seen["autocommit"] = connection.get_autocommit()
        return real_hook(payment, raw)

    monkeypatch.setattr(pay_services, "_hook_loan_request_fees", _spy)

    staff = get_user_model().objects.create(
        username="atomicstaff", is_staff=True, is_superuser=True
    )
    factory = APIRequestFactory()
    req = factory.post(
        f"/loans/requests/{lr.id}/study-fee/", {"reference": "R"}, format="json"
    )
    force_authenticate(req, user=staff)

    resp = loan_request_record_study_fee(req, pk=lr.id)

    assert resp.status_code == 200
    # L'invariant : le hook (select_for_update) NE doit PAS tourner en autocommit.
    assert seen.get("autocommit") is False, (
        "record_study_fee doit envelopper le hook dans transaction.atomic — "
        "sinon select_for_update lève TransactionManagementError sous PostgreSQL."
    )

    lr.refresh_from_db()
    assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
    assert lr.frais_demande_credit_paye is True
