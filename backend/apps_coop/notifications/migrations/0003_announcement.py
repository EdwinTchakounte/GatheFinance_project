# Generated manually — Announcement model (broadcast admin → membres).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coop_notifications", "0002_eventconfig_eventhook"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Announcement",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("titre", models.CharField(max_length=200)),
                (
                    "corps",
                    models.TextField(
                        help_text="Texte libre (multi-lignes). Le mobile l'affiche tel quel."
                    ),
                ),
                (
                    "audience",
                    models.CharField(
                        choices=[
                            ("all", "Tous les membres"),
                            ("actifs", "Membres actifs uniquement"),
                            ("suspendus", "Membres suspendus uniquement"),
                            ("selection", "Sélection manuelle (ids)"),
                        ],
                        db_index=True,
                        default="all",
                        max_length=12,
                    ),
                ),
                (
                    "audience_member_ids",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Utilisé uniquement quand audience=selection.",
                    ),
                ),
                (
                    "lien",
                    models.CharField(
                        blank=True,
                        help_text="Lien interne optionnel (ex: /campaigns/42) repris sur la notif.",
                        max_length=255,
                    ),
                ),
                (
                    "published_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Horodatage de diffusion effective (null = pas encore diffusée).",
                        null=True,
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Optionnel : date à laquelle l'annonce devient obsolète.",
                        null=True,
                    ),
                ),
                (
                    "recipients_count",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Nombre de Notifications créées au moment du broadcast.",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="announcements_authored",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Annonce",
                "verbose_name_plural": "Annonces",
                "ordering": ["-created_at"],
            },
        ),
    ]
