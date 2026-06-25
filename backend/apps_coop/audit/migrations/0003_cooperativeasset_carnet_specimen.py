"""Ajoute un specimen PDF du carnet sur CooperativeAsset (singleton)."""
from __future__ import annotations

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("coop_audit", "0002_cooperativeasset"),
    ]

    operations = [
        migrations.AddField(
            model_name="cooperativeasset",
            name="carnet_specimen",
            field=models.FileField(
                blank=True,
                help_text=(
                    "PDF specimen du carnet de cotisations — affiche sur la "
                    "page Commander carnet (mobile + portail) pour pre-visualisation."
                ),
                null=True,
                upload_to="coop/assets/",
            ),
        ),
        migrations.AddField(
            model_name="cooperativeasset",
            name="carnet_specimen_uploaded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="cooperativeasset",
            name="carnet_specimen_uploaded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
