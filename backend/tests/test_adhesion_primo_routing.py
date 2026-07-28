"""Fix cosmétique adhésion — un primo-adhérent n'est plus routé en « renouvellement ».

Bug : si le frais d'adhésion est payé EN DERNIER, un primo (SUSPENDU, jamais
activé) passait par _apply_membership_renewal → ACTIF mais sans l'événement
member.activated. Fix : marqueur date_activation (NULL = primo → activation).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AuditLog
from apps_coop.members.models import Member
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event

pytestmark = pytest.mark.django_db


def _pay(member, type_, montant):
    p = Payment.objects.create(
        member=member, montant=Decimal(montant), type=type_,
        statut=Payment.Statut.EN_ATTENTE, source=Payment.Source.MOBILE_MONEY,
        provider_code="tara", date_versement=timezone.now(),
    )
    handle_webhook_event(p.idempotency_key, "valide", provider_reference=f"TX-{p.id}", raw_payload={})
    return p


def _logs(member, action):
    return AuditLog.objects.filter(action=action, entite_type="Member", entite_id=member.id)


def test_primo_adhesion_payee_en_dernier_route_vers_activation(suspended_member):
    m = suspended_member
    assert m.date_activation is None  # primo
    # Adhésion payée EN DERNIER.
    _pay(m, Payment.Type.FRAIS_INSCRIPTION, "2000")
    _pay(m, Payment.Type.FRAIS_CARNET, "1000")
    _pay(m, Payment.Type.FRAIS_ADHESION, "10000")
    m.refresh_from_db()
    assert m.statut == Member.Statut.ACTIF
    assert m.date_activation is not None  # marqueur posé
    # Activation initiale (pas réactivation renouvellement).
    assert _logs(m, "member.activated").exists()
    assert not _logs(m, "member.reactivated_via_renewal").exists()


def test_membre_deja_active_route_vers_renouvellement(suspended_member):
    m = suspended_member
    m.date_activation = date(2025, 1, 1)  # a déjà été activé
    m.save(update_fields=["date_activation"])
    # Inscription + carnet d'abord, adhésion en dernier → réactivation cycle.
    _pay(m, Payment.Type.FRAIS_INSCRIPTION, "2000")
    _pay(m, Payment.Type.FRAIS_CARNET, "1000")
    _pay(m, Payment.Type.FRAIS_ADHESION, "10000")
    m.refresh_from_db()
    assert m.statut == Member.Statut.ACTIF
    assert _logs(m, "member.reactivated_via_renewal").exists()
