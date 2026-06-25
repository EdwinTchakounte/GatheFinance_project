"""Migration initiale — likes + commentaires sur contenus (GenericFK)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentReaction",
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
                ("object_id", models.PositiveIntegerField()),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_reactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reaction (like)",
                "verbose_name_plural": "Reactions (likes)",
            },
        ),
        migrations.CreateModel(
            name="ContentComment",
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
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("object_id", models.PositiveIntegerField()),
                ("body", models.TextField(max_length=1000)),
                ("hidden", models.BooleanField(db_index=True, default=False)),
                ("hidden_at", models.DateTimeField(blank=True, null=True)),
                ("hidden_reason", models.TextField(blank=True)),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "hidden_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="comments_hidden",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Commentaire",
                "verbose_name_plural": "Commentaires",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="contentreaction",
            index=models.Index(
                fields=["content_type", "object_id"],
                name="social_react_ct_obj_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="contentreaction",
            constraint=models.UniqueConstraint(
                fields=("user", "content_type", "object_id"),
                name="social_reaction_unique_per_target",
            ),
        ),
        migrations.AddIndex(
            model_name="contentcomment",
            index=models.Index(
                fields=["content_type", "object_id", "-created_at"],
                name="social_cmt_ct_obj_dt_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="contentcomment",
            index=models.Index(
                fields=["hidden", "-created_at"],
                name="social_cmt_hidden_dt_idx",
            ),
        ),
    ]
