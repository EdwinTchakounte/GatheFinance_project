from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CooperativeAsset",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reglement_interieur",
                    models.FileField(
                        blank=True,
                        help_text=(
                            "PDF du règlement intérieur — joint au mail de "
                            "bienvenue UC1. Si vide, le mail part sans pièce "
                            "jointe (attestation seule)."
                        ),
                        null=True,
                        upload_to="coop/assets/",
                    ),
                ),
                (
                    "reglement_uploaded_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "reglement_uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Asset coopérative",
                "verbose_name_plural": "Assets coopérative",
            },
        ),
    ]
