"""Backfill ``is_antidated=True`` sur les écritures antidatées DÉJÀ en base.

Avant ce lot, aucune écriture ne portait de marqueur ; le seul repère était le
journal d'audit (``action="savings.antidated_entry"``, avec ``entite_type`` +
``entite_id``). On rejoue cet audit pour taguer les écritures existantes des 3
modèles (collecte, classique, spécial), afin qu'elles apparaissent dans le
nouvel onglet « Saisies antidatées ». Idempotent et sans effet sur les soldes.
"""
from __future__ import annotations

from django.db import migrations


def backfill(apps, schema_editor):
    AuditLog = apps.get_model("audit", "AuditLog")
    SavingsTransaction = apps.get_model("savings", "SavingsTransaction")
    ClassicSavingsTransaction = apps.get_model("savings", "ClassicSavingsTransaction")
    SpecialCollectionTransaction = apps.get_model(
        "special_collections", "SpecialCollectionTransaction"
    )

    models_by_type = {
        "SavingsTransaction": SavingsTransaction,
        "ClassicSavingsTransaction": ClassicSavingsTransaction,
        "SpecialCollectionTransaction": SpecialCollectionTransaction,
    }
    # Regroupe les ids par type depuis l'audit des saisies antidatées.
    ids_by_type: dict[str, set[int]] = {k: set() for k in models_by_type}
    for entite_type, entite_id in (
        AuditLog.objects.filter(action="savings.antidated_entry")
        .values_list("entite_type", "entite_id")
    ):
        if entite_type in ids_by_type and entite_id:
            ids_by_type[entite_type].add(entite_id)

    for entite_type, ids in ids_by_type.items():
        if not ids:
            continue
        models_by_type[entite_type].objects.filter(pk__in=ids).update(
            is_antidated=True
        )


def noop_reverse(apps, schema_editor):
    # Pas de rollback destructif : on laisse le flag (inoffensif).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("savings", "0022_classicsavingstransaction_is_antidated_and_more"),
        ("special_collections", "0010_specialcollectiontransaction_is_antidated_and_more"),
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill, noop_reverse),
    ]
