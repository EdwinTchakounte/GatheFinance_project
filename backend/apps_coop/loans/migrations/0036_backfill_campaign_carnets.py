"""Rattrapage — carnet obligatoire pour les bénéficiaires créés via campagne.

Règle 2026 : un membre créé via campagne doit posséder un carnet (les écritures
collecte s'y imputent). Ce rattrapage crée un carnet pour les bénéficiaires
campagne existants (``member.microcampaign`` posé) qui n'en ont aucun, en
enregistrant le paiement carnet correspondant (facturé au tarif FeeType.CARNET,
source manuelle = régularisation).

Idempotent : ne touche que les membres campagne SANS carnet.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def backfill_carnets(apps, schema_editor):
    Member = apps.get_model("members", "Member")
    BookletOrder = apps.get_model("members", "BookletOrder")
    Payment = apps.get_model("payments", "Payment")
    FeeType = apps.get_model("payments", "FeeType")

    fee = (
        FeeType.objects.filter(code="CARNET", actif=True)
        .values_list("montant", flat=True)
        .first()
    )
    montant = Decimal(fee) if fee is not None else Decimal("0")

    now = timezone.now()
    beneficiaries = (
        Member.objects.filter(microcampaign__isnull=False)
        .exclude(booklet_orders__isnull=False)
        .distinct()
    )
    for member in beneficiaries:
        payment = Payment.objects.create(
            member=member,
            montant=montant,
            type="frais_carnet",
            source="manuel",
            statut="valide",
            date_versement=now,
            date_validation=now,
            provider_code="",
            reference_externe="RATTRAPAGE-CARNET-CAMPAGNE",
            motif_rejet="",
            idempotency_key=uuid.uuid4(),
        )
        BookletOrder.objects.create(
            member=member,
            payment=payment,
            statut="payee",
            annee=now.year,
        )


def noop_reverse(apps, schema_editor):
    # Pas de rollback : on ne supprime pas des carnets créés (données métier).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0035_loan_en_attente_decaissement"),
        ("members", "0016_staffrole"),
        ("payments", "0007_alter_payment_source"),
    ]

    operations = [
        migrations.RunPython(backfill_carnets, noop_reverse),
    ]
