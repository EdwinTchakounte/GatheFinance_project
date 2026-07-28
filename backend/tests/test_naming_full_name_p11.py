"""P11 — helper de nom complet dé-dupliqué « nom prénom »."""
from __future__ import annotations

import pytest

from apps_coop.members.naming import full_name

pytestmark = pytest.mark.django_db


def test_champs_separes_ordre_nom_prenom():
    assert full_name("Jean", "MBALLA") == "MBALLA Jean"


def test_nom_contient_deja_le_prenom_pas_de_duplication():
    # Formulaire public : nom = nom complet, admin remplit prenom → ne pas dupliquer.
    assert full_name("Jean", "MBALLA Jean") == "MBALLA Jean"
    assert full_name("Jean", "Jean MBALLA") == "Jean MBALLA"


def test_prenom_vide():
    assert full_name("", "MBALLA Jean") == "MBALLA Jean"
    assert full_name(None, "MBALLA") == "MBALLA"


def test_nom_vide():
    assert full_name("Jean", "") == "Jean"


def test_casse_insensible():
    assert full_name("jean", "MBALLA JEAN") == "MBALLA JEAN"


def test_member_nom_complet_property():
    from apps_coop.members.models import Member
    from tests.factories import MemberFactory

    m: Member = MemberFactory(prenom="Jean", nom="MBALLA")
    assert m.nom_complet == "MBALLA Jean"
    m2: Member = MemberFactory(prenom="Paul", nom="Paul NKOMO")
    assert m2.nom_complet == "Paul NKOMO"
