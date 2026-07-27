"""P4 — l'éligibilité s'appuie sur le TAUX D'APPORT, pas sur une couverture 100 %.

Avant : la voie auto-couverture n'ouvrait l'éligibilité que si l'épargne
disponible ≥ montant demandé → un nouvel adhérent avec un apport partiel était
rejeté (« aucune éligibilité ») uniquement à cause du montant.

Après : le réglage admin ``loans.eligibility.apport_rate`` (défaut 0.30) fixe le
seuil : l'épargne disponible doit atteindre ce ratio du montant. En-dessous de
100 %, la demande passe SOUS-COUVERTE (le comité juge) ; au-dessus, c'est de
l'auto-couverture pleine.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.loans.eligibility_routing import EligibilityRoute, evaluate_routes
from apps_coop.savings.models import ClassicSavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _setting(key: str, value: str):
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": value})


def _new_member(months_ago=2):
    m = MemberFactory()
    m.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    m.is_brc_member = False
    m.save(update_fields=["date_adhesion", "is_brc_member"])
    return m


def _savings(member, amount):
    ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(amount), date_ouverture=date.today()
    )


def test_apport_30pct_ouvre_leligibilite():
    """Nouvel adhérent, épargne = 30 % du montant → éligible (sous-couvert)."""
    member = _new_member()
    _savings(member, "30000")  # 30 % de 100 000

    ev = evaluate_routes(member, montant=Decimal("100000"))

    assert ev.eligible is True
    assert ev.route == EligibilityRoute.SENIOR_BRC
    assert ev.details.get("apport_couverture") is True
    assert ev.details.get("sous_couverture") is True
    assert Decimal(ev.details["apport_requis"]) == Decimal("30000")


def test_apport_sous_seuil_rejete():
    """Épargne < 30 % du montant → non éligible, motif basé sur l'apport."""
    member = _new_member()
    _savings(member, "20000")  # 20 % de 100 000 < 30 %

    ev = evaluate_routes(member, montant=Decimal("100000"))

    assert ev.eligible is False
    assert ev.route == EligibilityRoute.NONE
    assert any("apport requis" in m.lower() for m in ev.motifs)


def test_couverture_pleine_reste_auto_couverture():
    """Épargne ≥ montant → auto-couverture pleine (pas sous-couvert)."""
    member = _new_member()
    _savings(member, "120000")

    ev = evaluate_routes(member, montant=Decimal("100000"))

    assert ev.eligible is True
    assert ev.details.get("auto_couverture") is True
    assert "sous_couverture" not in ev.details


def test_taux_apport_editable_par_admin():
    """Réglage à 0.50 → il faut 50 % du montant."""
    _setting("loans.eligibility.apport_rate", "0.50")
    member = _new_member()
    _savings(member, "30000")  # 30 % < 50 % requis

    ev = evaluate_routes(member, montant=Decimal("100000"))
    assert ev.eligible is False

    acc = ClassicSavingsAccount.objects.get(member=member)
    acc.solde = Decimal("50000")
    acc.save(update_fields=["solde"])

    # Recharge à neuf : la relation inverse classic_savings_account est mise en
    # cache sur l'instance member au 1er accès (chaque requête réelle a un
    # member frais).
    from apps_coop.members.models import Member

    fresh = Member.objects.get(pk=member.pk)
    ev2 = evaluate_routes(fresh, montant=Decimal("100000"))
    assert ev2.eligible is True
    assert Decimal(ev2.details["apport_requis"]) == Decimal("50000")
