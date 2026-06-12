"""CH-12 — Distribution immédiate prêteurs en mode source + snapshot du taux.

En mode CH-11 'source', les intérêts sont retenus à la mise à disposition,
donc les échéances n'en contiennent pas. Pour que les prêteurs touchent
leur part 50 %, on doit la distribuer à T0 (au décaissement validé).

Deux changements de schéma :
  * ``LenderInterestPayout.installment`` devient nullable — le payout à T0
    n'est rattaché à aucune échéance.
  * Ajout de ``Loan.interest_share_rate_fige`` — snapshot du taux courant
    de l'AppSetting ``lender.interest_share_rate`` à l'approbation, pour
    que le partage applicable au crédit ne dépende pas d'un changement
    ultérieur côté admin.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0025_ch11_retenue_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lenderinterestpayout",
            name="installment",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Échéance dont la part intérêt a généré ce versement. "
                    "NULL en mode CH-11 source — le versement a lieu à T0 "
                    "(décaissement) et n'est rattaché à aucune échéance."
                ),
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="lender_interest_payouts",
                to="loans.loaninstallment",
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="interest_share_rate_fige",
            field=models.DecimalField(
                blank=True,
                decimal_places=4,
                help_text=(
                    "Taux de partage des intérêts prêteurs vs coop, figé à "
                    "l'approbation (CH-12). Ex. 0.5000 = 50 % aux prêteurs, "
                    "50 % à la coop. NULL = legacy ou pas de prêteurs."
                ),
                max_digits=5,
                null=True,
            ),
        ),
    ]
