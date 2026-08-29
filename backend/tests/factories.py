"""Factories factory_boy pour le domaine coopératif.

Une seule entry-point factory par modèle métier — les tests composent en
appelant les factories enfants explicitement (``SavingsAccountFactory(member=…)``).
Pas de SubFactory magique imbriquée qui crée des graphes d'objets opaques.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import factory
from django.contrib.auth import get_user_model

from apps_coop.members.models import BookletOrder, Member, MembershipRequest
from apps_coop.payments.models import Payment
from apps_coop.savings.models import SavingsAccount


User = get_user_model()


def grant_carnet(member, carnet_type=BookletOrder.Type.COLLECTE) -> BookletOrder:
    """Donne un carnet ``carnet_type`` au membre (via un Payment frais_carnet
    validé), comme le fait le hook ``_hook_carnet_fees`` en production.

    Décision 2026-08 : « une écriture ne se fait que dans un carnet ». Un membre
    activé détient normalement un carnet collecte (vendu aux frais d'activation) ;
    les tests de versement doivent donc partir d'un membre qui en possède un.
    """
    from django.utils import timezone

    fee_type = {
        BookletOrder.Type.COLLECTE: Payment.Type.FRAIS_CARNET,
        BookletOrder.Type.TONTINE: Payment.Type.FRAIS_CARNET_TONTINE,
        BookletOrder.Type.CAISSE_SCOLAIRE: Payment.Type.FRAIS_CARNET_CAISSE,
    }[carnet_type]
    now = timezone.now()
    payment = Payment.objects.create(
        member=member,
        montant=Decimal("0"),
        type=fee_type,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )
    return BookletOrder.objects.create(
        member=member,
        type=carnet_type,
        payment=payment,
        statut=BookletOrder.Statut.PAYEE,
        annee=now.year,
    )


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}@test.local")
    email = factory.LazyAttribute(lambda o: o.username)
    first_name = "Test"
    last_name = factory.Sequence(lambda n: f"User{n}")
    is_active = True


class MembershipRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MembershipRequest

    nom = factory.Sequence(lambda n: f"Kamga{n}")
    prenom = "Jean"
    email = factory.Sequence(lambda n: f"applicant{n}@test.local")
    phone = "+237699000000"
    city = "Douala"
    motivation = "Souhaite épargner régulièrement."
    language = "fr"
    statut = MembershipRequest.Statut.EN_ATTENTE


class MemberFactory(factory.django.DjangoModelFactory):
    """Membre `actif` avec un compte d'épargne vide attaché."""

    class Meta:
        model = Member
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    numero_membre = factory.Sequence(lambda n: f"GF-2026-{n:04d}")
    nom = factory.LazyAttribute(lambda o: o.user.last_name)
    prenom = factory.LazyAttribute(lambda o: o.user.first_name)
    phone = "+237699000000"
    statut = Member.Statut.ACTIF
    date_adhesion = factory.LazyFunction(date.today)

    @factory.post_generation
    def with_savings(self, create, extracted, **kwargs):
        if not create:
            return
        SavingsAccount.objects.get_or_create(
            member=self,
            defaults={
                "solde": Decimal("0"),
                "date_ouverture": date.today(),
                "taux_interet_applique": Decimal("0"),
            },
        )

    @factory.post_generation
    def with_carnet(self, create, extracted, **kwargs):
        """Carnet collecte par défaut pour un membre ACTIF.

        Reflète la production (un membre activé détient un carnet, vendu aux
        frais d'activation) et satisfait la garde « une écriture ne se fait que
        dans un carnet » du canal versement. Les tests qui pilotent eux-mêmes
        les carnets (comptage, ordonnancement) passent ``with_carnet=False``.
        """
        if not create or extracted is False:
            return
        if self.statut != Member.Statut.ACTIF:
            return
        grant_carnet(self, BookletOrder.Type.COLLECTE)


class SuspendedMemberFactory(MemberFactory):
    """Membre `suspendu` — n'a pas encore payé sa 1re cotisation."""

    statut = Member.Statut.SUSPENDU
