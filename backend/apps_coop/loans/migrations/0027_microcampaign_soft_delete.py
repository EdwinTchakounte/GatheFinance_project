"""Soft-delete MicrocreditCampaign.

Ajoute le champ ``deleted_at`` (DateTimeField, nullable, indexed).
L'admin peut 'supprimer' une campagne sans casser les LoanRequest deja
soumises ni perdre l'historique pour l'audit. Une campagne soft-deletee
est filtree de toutes les listes par defaut (vitrine, mobile, admin).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0026_ch12_lender_share_at_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="microcreditcampaign",
            name="deleted_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text=(
                    "Date a laquelle l'admin a 'supprime' la campagne (soft-delete). "
                    "Si non null, la campagne est masquee de toutes les listes "
                    "publiques et admin par defaut. Les demandes deja soumises "
                    "restent rattachees."
                ),
                null=True,
            ),
        ),
    ]
