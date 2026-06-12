"""CH-8 — Champ `date_butoire` explicite sur Loan + backfill data depuis la
dernière échéance des Loans existants.
"""
from django.db import migrations, models


def backfill_date_butoire(apps, schema_editor):
    """Pose date_butoire = date_echeance de la dernière LoanInstallment du Loan,
    pour préserver le comportement contentieux existant sur les crédits
    historiques.
    """
    Loan = apps.get_model("loans", "Loan")
    for loan in Loan.objects.all():
        if loan.date_butoire is not None:
            continue
        last = (
            loan.installments.order_by("-date_echeance")
            .values_list("date_echeance", flat=True)
            .first()
        )
        if last is not None:
            loan.date_butoire = last
            loan.save(update_fields=["date_butoire", "updated_at"])


def noop_reverse(apps, schema_editor):
    """Reverse : on remet à None (non destructif — date_limite_globale fallback
    sur la dernière échéance)."""
    Loan = apps.get_model("loans", "Loan")
    Loan.objects.update(date_butoire=None)


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0022_ch6_double_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="loan",
            name="date_butoire",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text=(
                    "Date butoire formelle pour solder le crédit. Les échéances "
                    "individuelles sont indicatives ; seule la date butoire engage. "
                    "Modifiable par l'admin via /extend-deadline/ avec audit."
                ),
                null=True,
            ),
        ),
        migrations.RunPython(backfill_date_butoire, noop_reverse),
    ]
