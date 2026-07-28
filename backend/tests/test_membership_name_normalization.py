"""Normalisation du nom à l'adhésion (bug live 2026-07-28).

Le formulaire public ne collecte souvent qu'un champ « nom » = nom complet
(« Edwin tchako ») et l'admin renseigne le prénom (« Edwin ») à l'instruction.
Sans nettoyage, le prénom reste inclus en tête du nom → l'affichage « nom + prénom »
le duplique (« Edwin Edwin tchako »). On vérifie que le prénom est retiré du nom.
"""
from __future__ import annotations

import pytest

from apps_coop.members.models import MembershipRequest
from apps_coop.members.services import approve_membership_request


pytestmark = pytest.mark.django_db(transaction=True)


def _req(**kw):
    defaults = dict(
        nom="Edwin tchako",
        prenom="",
        email="edwin.norm@t.local",
        phone="699000111",
        city="Douala",
        statut=MembershipRequest.Statut.EN_ATTENTE,
    )
    defaults.update(kw)
    return MembershipRequest.objects.create(**defaults)


def test_prenom_retire_du_nom_a_l_approbation(admin_user):
    req = _req(nom="Edwin tchako", prenom="")
    member = approve_membership_request(req, instructed_by=admin_user, prenom="Edwin")
    assert member.prenom == "Edwin"
    assert member.nom == "tchako"  # le prénom en tête a été retiré


def test_nom_intact_quand_prenom_absent_du_nom(admin_user):
    req = _req(nom="Mballa", prenom="", email="mballa.norm@t.local")
    member = approve_membership_request(req, instructed_by=admin_user, prenom="Jean")
    assert member.prenom == "Jean"
    assert member.nom == "Mballa"  # inchangé
