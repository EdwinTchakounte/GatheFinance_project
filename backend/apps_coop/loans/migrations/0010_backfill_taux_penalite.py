"""Backfill ``Loan.taux_penalite`` pour les crédits existants (EXT-versioning).

Tous les crédits décaissés avant cette migration héritent du taux global
courant (lu via ``get_rate``, défaut réglementaire 0.50). Ce backfill n'écrase
JAMAIS une valeur déjà présente : si une ligne a déjà été éditée à la main,
on la respecte.
"""
from decimal import Decimal

from django.db import migrations


def forwards(apps, schema_editor):
    Loan = apps.get_model("loans", "Loan")
    # Import paresseux du helper (apps non chargés dans la migration sandbox).
    try:
        from apps_coop.payments.rates import get_rate

        taux = Decimal(get_rate("LATE_PENALTY"))
    except Exception:  # noqa: BLE001
        taux = Decimal("0.50")  # fallback réglementaire

    Loan.objects.filter(taux_penalite__isnull=True).update(taux_penalite=taux)


def backwards(apps, _schema_editor):
    # Réversible : on remet à NULL (pas de perte d'info, le champ reste nullable).
    Loan = apps.get_model("loans", "Loan")
    Loan.objects.all().update(taux_penalite=None)


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0009_loan_taux_penalite_alter_loan_taux_interet"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
