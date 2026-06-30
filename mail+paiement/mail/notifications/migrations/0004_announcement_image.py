"""Announcement.image . ImageField optionnel pour illustrer les annonces."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coop_notifications", "0003_announcement"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="coop/announcements/",
                help_text=(
                    "Image illustrative optionnelle (JPG/PNG, recommande 1200x630px). "
                    "Affichee en haut de la notification mobile et integree dans "
                    "l'e-mail si diffusion email activee."
                ),
            ),
        ),
    ]
