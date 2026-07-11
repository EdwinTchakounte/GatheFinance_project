"""Tests du cycle de vie membre — flux UC1.

Couvre :
  - Approbation de demande d'adhésion (création User + Member + SavingsAccount, idempotence)
  - Rejet (motif requis, double-rejet idempotent)
  - Activation du membre suspendu via paiement de la 1re cotisation
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps_coop.members.models import Member, MembershipRequest
from apps_coop.members.services import (
    approve_membership_request,
    reject_membership_request,
)
from apps_coop.payments.models import Payment
from apps_coop.payments.services import handle_webhook_event
from apps_coop.savings.models import SavingsAccount


pytestmark = pytest.mark.django_db


# -- Approbation ------------------------------------------------------------


class TestApproveMembershipRequest:
    def test_creates_user_member_and_savings_account(self, pending_request, admin_user):
        member = approve_membership_request(
            pending_request,
            instructed_by=admin_user,
            prenom="Marie",
            nom="Tankam",
        )

        # User créé avec email = email de la demande
        User = get_user_model()
        user = User.objects.get(email=pending_request.email)
        assert user.first_name == "Marie"
        assert user.last_name == "Tankam"

        # Member rattaché, statut SUSPENDU (paiement 1re cotisation pas encore reçu)
        assert member.user == user
        assert member.statut == Member.Statut.SUSPENDU
        assert member.numero_membre.startswith("GF-")

        # Demande close avec traçabilité
        pending_request.refresh_from_db()
        assert pending_request.statut == MembershipRequest.Statut.APPROUVEE
        assert pending_request.instruit_par == admin_user
        assert pending_request.date_decision is not None

        # SavingsAccount existant avec solde 0
        account = SavingsAccount.objects.get(member=member)
        assert account.solde == 0

    def test_idempotent_double_approval_returns_existing_member(
        self, pending_request, admin_user
    ):
        m1 = approve_membership_request(pending_request, instructed_by=admin_user, nom="Tankam")
        pending_request.refresh_from_db()
        m2 = approve_membership_request(pending_request, instructed_by=admin_user, nom="Tankam")
        assert m1.pk == m2.pk
        # Un seul Member, un seul SavingsAccount.
        assert Member.objects.count() == 1
        assert SavingsAccount.objects.count() == 1

    def test_rejects_when_request_already_rejected(self, pending_request, admin_user):
        reject_membership_request(pending_request, instructed_by=admin_user, motif="Spam")
        pending_request.refresh_from_db()
        with pytest.raises(ValueError, match="Cannot approve"):
            approve_membership_request(pending_request, instructed_by=admin_user, nom="X")

    def test_nom_is_required(self, pending_request, admin_user):
        pending_request.nom = ""
        pending_request.save()
        with pytest.raises(ValueError, match="nom est requis"):
            approve_membership_request(pending_request, instructed_by=admin_user)

    def test_duplicate_email_already_member_raises_not_500(
        self, pending_request, admin_user
    ):
        """Ré-inscription avec un email déjà membre → erreur claire (pas 500).

        Régression : `member` est OneToOne → approuver une 2e demande pour un
        email déjà rattaché à un Member crashait en IntegrityError. On veut un
        ValueError explicite → l'admin rejette le doublon.
        """
        # 1re demande approuvée → Member créé et rattaché.
        approve_membership_request(pending_request, instructed_by=admin_user, nom="Sino")

        # 2e demande, MÊME email → doublon.
        dup = MembershipRequest.objects.create(
            nom="Sino",
            prenom="Josue",
            email=pending_request.email,
            phone="+237699000001",
            statut=MembershipRequest.Statut.EN_ATTENTE,
        )
        with pytest.raises(ValueError, match="déjà rattaché au membre"):
            approve_membership_request(dup, instructed_by=admin_user, nom="Sino")
        # Aucun doublon créé.
        assert Member.objects.count() == 1


# -- Rejet ------------------------------------------------------------------


class TestRejectMembershipRequest:
    def test_motif_required(self, pending_request, admin_user):
        with pytest.raises(ValueError, match="motif"):
            reject_membership_request(pending_request, instructed_by=admin_user, motif="   ")

    def test_no_user_or_member_created(self, pending_request, admin_user):
        reject_membership_request(
            pending_request, instructed_by=admin_user, motif="Pièces manquantes."
        )
        assert Member.objects.count() == 0
        User = get_user_model()
        assert not User.objects.filter(email=pending_request.email).exists()

    def test_double_rejection_is_idempotent(self, pending_request, admin_user):
        reject_membership_request(
            pending_request, instructed_by=admin_user, motif="Premier rejet"
        )
        pending_request.refresh_from_db()
        # 2e appel = no-op, pas d'exception
        same = reject_membership_request(
            pending_request, instructed_by=admin_user, motif="Autre"
        )
        assert same.motif_rejet == "Premier rejet"


# -- Activation via paiement frais_adhesion ---------------------------------


class TestMemberActivationOnFirstCotisation:
    def test_payment_frais_adhesion_alone_keeps_member_suspended(self, suspended_member):
        """Depuis CH-2 (juin 2026) : un seul frais payé ne suffit plus pour activer.
        Il faut les 3 frais cumulés (adhésion + inscription + carnet) — cf.
        ``test_membership_activation.py`` pour la couverture complète."""
        # 1) On crée un paiement frais_adhesion en attente
        payment = Payment.objects.create(
            member=suspended_member,
            montant=Decimal("10000"),
            type=Payment.Type.FRAIS_ADHESION,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code="tara",
            date_versement=timezone.now(),
        )
        # 2) On simule le webhook "valide" (chemin que dev_confirm et le webhook prod empruntent)
        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference="TEST-REF-001",
            raw_payload={},
        )
        # 3) Le membre reste suspendu — il manque les frais d'inscription et carnet.
        suspended_member.refresh_from_db()
        payment.refresh_from_db()
        assert suspended_member.statut == Member.Statut.SUSPENDU
        assert payment.statut == Payment.Statut.VALIDE
        assert payment.reference_externe == "TEST-REF-001"
