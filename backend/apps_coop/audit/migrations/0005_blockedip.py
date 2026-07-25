# Sécurité — blacklist IP (ban global via DB). 2026-07-24.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0004_require_brc_default_false"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockedIP",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ip", models.GenericIPAddressField(db_index=True, unique=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                (
                    "auto",
                    models.BooleanField(
                        default=False,
                        help_text="Posé automatiquement (trafic anormal) plutôt que manuellement.",
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        help_text="Fin du ban. Vide = ban permanent.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "IP bloquée",
                "verbose_name_plural": "IP bloquées",
                "ordering": ["-created_at"],
            },
        ),
    ]
