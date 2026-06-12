"""CH-11 — Retenue des intérêts à la source à la mise à disposition.

Sinora §5.3 : à la mise à disposition, la coop retient les 10 % d'intérêts.
Le membre reçoit donc 90 % du montant nominal et ne rembourse que ce
qu'il a touché (capital pur). Les crédits historiques antérieurs à ce
chantier conservent le mode "echeances" (intérêts répartis sur les
remboursements) pour préserver les soldes en cours.
"""
from decimal import Decimal

from django.db import migrations, models


def backfill_retenue_source(apps, schema_editor):
    """Pose les valeurs cohérentes pour les Loans existants.

    Tous les Loans antérieurs à CH-11 sont étiquetés 'echeances' :
      * ``montant_decaisse_net`` = ``montant`` (ce qu'ils avaient reçu).
      * ``interets_retenus_source`` = 0 (aucune retenue n'avait eu lieu).
    Le ``mode_retenue_interets`` étant déjà à 'echeances' par défaut, on
    ne touche que les deux montants.
    """
    Loan = apps.get_model("loans", "Loan")
    zero = Decimal("0")
    for loan in Loan.objects.all().iterator():
        if loan.montant_decaisse_net is None:
            loan.montant_decaisse_net = loan.montant
        if loan.interets_retenus_source is None:
            loan.interets_retenus_source = zero
        loan.save(
            update_fields=[
                "montant_decaisse_net",
                "interets_retenus_source",
                "updated_at",
            ]
        )


def noop_reverse(apps, schema_editor):
    """Reverse non-destructif — on remet les 2 montants à NULL.

    Le champ ``mode_retenue_interets`` est supprimé automatiquement par
    le RemoveField que Django génère lors d'une migrate vers 0024.
    """
    Loan = apps.get_model("loans", "Loan")
    Loan.objects.update(montant_decaisse_net=None, interets_retenus_source=None)


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0024_ch9_moyen_reception"),
    ]

    operations = [
        migrations.AddField(
            model_name="loan",
            name="mode_retenue_interets",
            field=models.CharField(
                choices=[
                    ("echeances", "Intérêts répartis sur les échéances (legacy)"),
                    (
                        "source",
                        "Intérêts retenus à la source à la mise à disposition",
                    ),
                ],
                default="echeances",
                help_text=(
                    "Mode de paiement des intérêts. 'source' = retenus à "
                    "la mise à disposition (CH-11), 'echeances' = répartis "
                    "sur les remboursements (comportement historique)."
                ),
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="montant_decaisse_net",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Montant réellement versé au membre au décaissement. "
                    "En mode 'source' = montant - interets_retenus_source. "
                    "En mode 'echeances' = montant. NULL = legacy pre-CH-11."
                ),
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="interets_retenus_source",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Intérêts ponctionnés par la coop à la mise à "
                    "disposition. En mode 'source' = montant × "
                    "taux_interet. En mode 'echeances' = 0. NULL = legacy."
                ),
                max_digits=14,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_retenue_source, noop_reverse),
    ]
