"""LOT 3 (refonte 2026) — Backfill ``ClassicSavingsAccount.date_prochaine_maturite``.

Pour les comptes d'épargne classique créés AVANT la refonte 2026, le champ
``date_prochaine_maturite`` est NULL. On le pose à
``date_ouverture + epargne.contract_months mois`` afin que le cron annuel
(LOT 5) ait un repère pour calculer l'anniversaire.

Idempotent : seuls les comptes avec ``date_prochaine_maturite IS NULL`` sont
modifiés. Re-runnable en toute sécurité.

Reverse : NOOP (champ nullable, on n'écrase rien si on rollback).
"""
from __future__ import annotations

from django.db import migrations

# Défaut métier — aligné sur ``epargne.contract_months`` (LOT 2). On le code
# en dur ici car les migrations s'exécutent **avant** que les services soient
# disponibles côté Python ; et que le AppSetting peut ne pas être seedé au
# moment du upgrade.
_DEFAULT_CONTRACT_MONTHS = 12


def _add_months(d, months: int):
    """Avance une ``date`` de N mois en restant déterministe (pas de
    dateutil). Si le mois cible n'a pas le même jour, on prend le dernier
    jour valide de ce mois (logique commerciale standard).
    """
    from calendar import monthrange

    total_months = (d.year * 12 + d.month - 1) + months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    last_day = monthrange(new_year, new_month)[1]
    return d.replace(year=new_year, month=new_month, day=min(d.day, last_day))


def forward(apps, schema_editor):
    ClassicSavingsAccount = apps.get_model("savings", "ClassicSavingsAccount")
    AppSetting = apps.get_model("audit", "AppSetting")

    # On essaye de lire la valeur configurée si disponible, sinon défaut.
    try:
        raw = (
            AppSetting.objects.filter(cle="epargne.contract_months")
            .values_list("valeur", flat=True)
            .first()
        )
        contract_months = int(raw) if raw else _DEFAULT_CONTRACT_MONTHS
    except Exception:  # noqa: BLE001 — AppSetting peut ne pas exister encore
        contract_months = _DEFAULT_CONTRACT_MONTHS

    # Idempotent : on ne touche que les NULL.
    qs = ClassicSavingsAccount.objects.filter(date_prochaine_maturite__isnull=True)
    for account in qs.iterator():
        account.date_prochaine_maturite = _add_months(
            account.date_ouverture, contract_months
        )
        account.save(update_fields=["date_prochaine_maturite"])


def reverse(apps, schema_editor):
    # On ne ré-écrase pas, le champ reste nullable.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("savings", "0005_alter_savingsaccount_options_and_more"),
        # Dépend de la table AppSetting pour lire la durée configurée.
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
