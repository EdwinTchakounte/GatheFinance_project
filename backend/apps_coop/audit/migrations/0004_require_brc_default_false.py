"""BRC documentaire (2026-07) : l'ancienneté seule ouvre la voie « Ancien ».

Le justificatif BRC n'est plus un statut à valider (page passée en lecture
seule, boutons approuver/rejeter retirés). On bascule donc le réglage
``loans.eligibility.require_brc_for_senior`` de son ancien défaut ``true`` vers
``false`` sur les installations existantes, pour que la voie « crédit de
confiance » d'un Ancien sous-couvert reste ouverte (le comité juge la demande).

Prudence : on ne bascule QUE si la valeur est encore l'ancien défaut ``true``
(on respecte un éventuel choix admin explicite différent). Idempotent.
"""
from __future__ import annotations

from django.db import migrations


KEY = "loans.eligibility.require_brc_for_senior"


def set_false(apps, schema_editor):
    AppSetting = apps.get_model("audit", "AppSetting")
    obj = AppSetting.objects.filter(cle=KEY).first()
    if obj is None:
        AppSetting.objects.create(
            cle=KEY,
            valeur="false",
            description=(
                "BRC documentaire : l'ancienneté seule ouvre la Voie 1, "
                "le comité juge la demande."
            ),
        )
    elif (obj.valeur or "").strip().lower() == "true":
        obj.valeur = "false"
        obj.save(update_fields=["valeur", "updated_at"])


def noop(apps, schema_editor):
    # Pas de retour arrière : on ne re-exige pas le BRC automatiquement.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0003_cooperativeasset_carnet_specimen"),
    ]

    operations = [
        migrations.RunPython(set_false, noop),
    ]
