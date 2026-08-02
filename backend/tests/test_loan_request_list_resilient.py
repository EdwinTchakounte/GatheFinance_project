"""Régression #82 — la liste membre des demandes de crédit est résiliente.

Symptôme terrain : le membre ne voit AUCUNE demande sur « Mes crédits »
(y compris sa demande EN_ATTENTE à régler), alors qu'elles existent en base.
Cause : ``loan_request_list`` sérialisait en ``many=True`` (tout-ou-rien) sans
context → si UNE demande limite faisait échouer la sérialisation, TOUTE la
réponse partait en 500 → le client affichait une liste vide (cul-de-sac).

Fix : sérialisation par item + context ; un item fautif est écarté (loggé),
les autres restent visibles.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans import serializers as loan_serializers
from apps_coop.loans.models import LoanRequest
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _api(member):
    c = APIClient()
    c.force_authenticate(user=member.user)
    return c


def _req(member, montant, statut):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal(montant),
        duree_mois=2,
        motif="x",
        statut=statut,
    )


def test_one_broken_request_does_not_blank_the_whole_list(monkeypatch):
    member = MemberFactory()
    member.date_adhesion = date.today() - timedelta(days=30)
    member.save(update_fields=["date_adhesion"])
    good = _req(member, "50000", LoanRequest.Statut.EN_ATTENTE)
    poison = _req(member, "25000", LoanRequest.Statut.APPROUVEE)

    # Simule une donnée limite : la sérialisation d'UNE demande lève.
    real_get_voie = loan_serializers.LoanRequestReadSerializer.get_voie

    def _boom(self, obj):
        if obj.id == poison.id:
            raise ValueError("donnée limite simulée")
        return real_get_voie(self, obj)

    monkeypatch.setattr(
        loan_serializers.LoanRequestReadSerializer, "get_voie", _boom
    )

    r = _api(member).get("/api/v1/loans/me/requests/")
    # Pas de 500 : la demande fautive est écartée, la bonne (EN_ATTENTE) survit.
    assert r.status_code == 200, r.content
    ids = [x["id"] for x in r.json()]
    assert good.id in ids
    assert poison.id not in ids


def test_list_ok_returns_all_when_nothing_breaks():
    member = MemberFactory()
    member.date_adhesion = date.today() - timedelta(days=30)
    member.save(update_fields=["date_adhesion"])
    a = _req(member, "50000", LoanRequest.Statut.EN_ATTENTE)
    b = _req(member, "25000", LoanRequest.Statut.APPROUVEE)
    r = _api(member).get("/api/v1/loans/me/requests/")
    assert r.status_code == 200, r.content
    ids = {x["id"] for x in r.json()}
    assert ids == {a.id, b.id}
