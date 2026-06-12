"""CH-9 — Moyen de réception du décaissement choisi à la soumission.

Le membre choisit dès la demande où il veut recevoir l'argent (Tara OM,
Tara MoMo, espèces en agence). Le canal apparaît sur la note de demande
PDF et pré-remplit le payout Tara à la mise à disposition.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0023_ch8_date_butoire"),
    ]

    operations = [
        migrations.AddField(
            model_name="loanrequest",
            name="moyen_reception",
            field=models.CharField(
                blank=True,
                choices=[
                    ("tara_om", "Tara Orange Money"),
                    ("tara_momo", "Tara MTN MoMo"),
                    ("agence_especes", "Retrait espèces en agence"),
                ],
                help_text=(
                    "Canal choisi par le membre pour recevoir le décaissement. "
                    "Pilote l'auto-fill du payout Tara à la mise à disposition."
                ),
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="loanrequest",
            name="recipient_phone",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Numéro Mobile Money du membre — requis si moyen_reception "
                    "= tara_om ou tara_momo. Vide pour agence_especes."
                ),
                max_length=32,
            ),
        ),
    ]
