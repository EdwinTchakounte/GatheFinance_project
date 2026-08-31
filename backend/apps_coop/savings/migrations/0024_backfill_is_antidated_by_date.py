"""Backfill FIABLE de ``is_antidated`` — indépendant de l'audit.

Le premier backfill (0023) s'appuyait sur l'``AuditLog`` (action
``savings.antidated_entry``). Or ``archive_audit_logs`` archive puis SUPPRIME
les audits de plus de ~3 jours : les écritures antidatées anciennes n'étaient
donc plus rattachées à un audit → non taguées → absentes de l'onglet.

Ce backfill utilise une signature qui ne dépend PAS de l'audit : une écriture
antidatée a une **date métier antérieure à sa date de saisie** (``date`` <
``created_at``, au jour près) ET **aucun ``Payment``** rattaché. Toute écriture
normale (dépôt via paiement, retrait/intérêt/commission/contre-passation datés
du jour) a ``date`` ≈ ``created_at`` → exclue. On ne fait que POSER le flag,
jamais l'enlever ; aucun solde ni donnée n'est touché.
"""
from __future__ import annotations

from django.db import migrations
from django.db.models import F
from django.db.models.functions import TruncDate


def _flag(model):
    # date (jour) STRICTEMENT antérieure à created_at (jour), sans Payment,
    # pas déjà taguée. .values_list(pk) puis update(pk__in) pour rester
    # compatible toutes bases (pas d'update après annotate).
    ids = list(
        model.objects.filter(payment__isnull=True, is_antidated=False)
        .annotate(_d=TruncDate("date"), _c=TruncDate("created_at"))
        .filter(_d__lt=F("_c"))
        .values_list("pk", flat=True)
    )
    if ids:
        model.objects.filter(pk__in=ids).update(is_antidated=True)
    return len(ids)


def backfill(apps, schema_editor):
    SavingsTransaction = apps.get_model("savings", "SavingsTransaction")
    ClassicSavingsTransaction = apps.get_model("savings", "ClassicSavingsTransaction")
    SpecialCollectionTransaction = apps.get_model(
        "special_collections", "SpecialCollectionTransaction"
    )
    for model in (
        SavingsTransaction,
        ClassicSavingsTransaction,
        SpecialCollectionTransaction,
    ):
        _flag(model)


def noop_reverse(apps, schema_editor):
    # Pas de rollback destructif : on laisse le flag (inoffensif).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("savings", "0023_backfill_is_antidated"),
        ("special_collections", "0010_specialcollectiontransaction_is_antidated_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
