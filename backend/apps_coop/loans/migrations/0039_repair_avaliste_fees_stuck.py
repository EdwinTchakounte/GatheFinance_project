"""Répare les demandes avaliste coincées en « frais à percevoir ».

Régression 2026-07-20 : une demande par la voie avaliste dont l'avaliste avait
accepté ET dont les frais d'étude étaient encaissés restait bloquée en
``EN_ATTENTE`` (``frais_demande_credit_paye=True``) — cf.
``open_instruction_after_fees`` qui re-sollicitait l'avaliste et avalait le
``ValueError`` « consentement déjà existant ».

Cette data-migration ré-aligne le statut des demandes déjà coincées, selon
l'état de leur consentement avaliste. Idempotente : ne touche que les demandes
EN_ATTENTE avec frais payés ET consentement présent.
"""
from __future__ import annotations

from django.db import migrations


def repair(apps, schema_editor):
    LoanRequest = apps.get_model("loans", "LoanRequest")

    # STRICTEMENT les demandes avaliste : EN_ATTENTE + frais payés + consentement
    # présent. On ne touche PAS les demandes sans consent (un bénéficiaire
    # campagne en attente de carnet est légitimement EN_ATTENTE frais payés).
    stuck = LoanRequest.objects.filter(
        statut="en_attente",
        frais_demande_credit_paye=True,
        avaliste_consent__isnull=False,
    ).select_related("avaliste_consent")
    for lr in stuck:
        consent = lr.avaliste_consent
        if consent.statut == "accepted":
            lr.statut = "en_instruction"
        elif consent.statut == "refused":
            lr.statut = "rejetee_avaliste"
        else:  # pending
            lr.statut = "en_attente_avaliste"
        lr.save(update_fields=["statut", "updated_at"])


def noop(apps, schema_editor):
    # Pas de retour arrière : on ne re-bloque pas une demande débloquée.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0038_loanrenewal_interets_dus_and_more"),
    ]

    operations = [
        migrations.RunPython(repair, noop),
    ]
