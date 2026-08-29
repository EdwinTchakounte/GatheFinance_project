"""Carnets typés (2026-08) — un carnet distinct par type (collecte, tontine,
caisse scolaire). L'achat d'un carnet tontine/caisse crée un BookletOrder du
bon type et n'active/ne renouvelle rien ; l'imputation des écritures est
isolée par type."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.members.models import BookletOrder, Member
from apps_coop.payments.models import Payment
from apps_coop.payments.services import _hook_carnet_fees
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _valid_payment(member, type_):
    return Payment.objects.create(
        member=member,
        montant=Decimal("1000"),
        type=type_,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )


class TestTypedCarnetHook:
    def test_carnet_tontine_cree_un_ordre_typé(self):
        m = MemberFactory(with_carnet=False)
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET_TONTINE), {})
        order = BookletOrder.objects.get(member=m)
        assert order.type == BookletOrder.Type.TONTINE

    def test_carnet_caisse_cree_un_ordre_typé(self):
        m = MemberFactory(with_carnet=False)
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET_CAISSE), {})
        assert BookletOrder.objects.get(member=m).type == (
            BookletOrder.Type.CAISSE_SCOLAIRE
        )

    def test_carnet_collecte_reste_le_defaut(self):
        m = MemberFactory(with_carnet=False)
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET), {})
        assert BookletOrder.objects.get(member=m).type == BookletOrder.Type.COLLECTE

    def test_carnet_tontine_nactive_pas_un_membre_suspendu(self):
        """Un carnet tontine n'est PAS un des 3 frais d'activation : payer un
        carnet tontine ne doit pas basculer un membre SUSPENDU en ACTIF."""
        m = MemberFactory(with_carnet=False)
        m.statut = Member.Statut.SUSPENDU
        m.save(update_fields=["statut"])
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET_TONTINE), {})
        m.refresh_from_db()
        assert m.statut == Member.Statut.SUSPENDU


class TestTypedCarnetImputation:
    def test_latest_for_est_isolé_par_type(self):
        m = MemberFactory(with_carnet=False)
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET), {})
        _hook_carnet_fees(_valid_payment(m, Payment.Type.FRAIS_CARNET_TONTINE), {})

        collecte = BookletOrder.latest_for(m, BookletOrder.Type.COLLECTE)
        tontine = BookletOrder.latest_for(m, BookletOrder.Type.TONTINE)
        assert collecte is not None and collecte.type == BookletOrder.Type.COLLECTE
        assert tontine is not None and tontine.type == BookletOrder.Type.TONTINE
        assert collecte.id != tontine.id
        # Défaut = collecte : une écriture d'épargne ne s'impute jamais au
        # carnet tontine même s'il est plus récent.
        assert BookletOrder.latest_for(m).id == collecte.id
        # Aucun carnet caisse → None (écriture tolérée non rattachée).
        assert BookletOrder.latest_for(m, BookletOrder.Type.CAISSE_SCOLAIRE) is None
