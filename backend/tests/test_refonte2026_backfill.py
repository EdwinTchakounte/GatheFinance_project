"""LOT 3 (refonte 2026) — Backfill ``date_prochaine_maturite`` + commande
``backfill_refonte2026`` (dry-run + apply).

Couvre :
  - La commande pose ``date_prochaine_maturite = ouverture + 12 mois``
  - Elle ignore les comptes déjà à jour (idempotence)
  - ``--dry-run`` n'écrit RIEN en base
  - Respect du tunable ``epargne.contract_months``
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps_coop.audit.models import AppSetting
from apps_coop.savings.models import ClassicSavingsAccount

pytestmark = pytest.mark.django_db


def _make_account(member, ouverture: date, maturite: date | None = None):
    """Helper — crée un ``ClassicSavingsAccount`` avec une maturité optionnelle."""
    return ClassicSavingsAccount.objects.create(
        member=member,
        solde=Decimal("0"),
        date_ouverture=ouverture,
        date_prochaine_maturite=maturite,
    )


class TestBackfillCommand:

    def test_backfills_null_maturity(self, active_member):
        # Compte legacy sans maturité.
        acc = _make_account(active_member, date(2026, 1, 15))
        assert acc.date_prochaine_maturite is None

        call_command("backfill_refonte2026", stdout=StringIO())

        acc.refresh_from_db()
        # 15/01/2026 + 12 mois = 15/01/2027.
        assert acc.date_prochaine_maturite == date(2027, 1, 15)

    def test_idempotent_skips_already_filled(self, active_member):
        existing = date(2027, 6, 1)
        acc = _make_account(active_member, date(2026, 1, 15), maturite=existing)

        out = StringIO()
        call_command("backfill_refonte2026", stdout=out)

        acc.refresh_from_db()
        # La maturité existante ne doit PAS bouger.
        assert acc.date_prochaine_maturite == existing
        # Le message attendu est "Rien à faire" (0 NULL).
        assert "Rien à faire" in out.getvalue()

    def test_dry_run_does_not_write(self, active_member):
        acc = _make_account(active_member, date(2026, 1, 15))
        out = StringIO()
        call_command("backfill_refonte2026", "--dry-run", stdout=out)

        acc.refresh_from_db()
        # Rien n'a changé.
        assert acc.date_prochaine_maturite is None
        # Mais le rapport indique 1 cible.
        assert "DRY-RUN" in out.getvalue()
        assert "1 compte" in out.getvalue()

    def test_respects_appsetting_contract_months(self, active_member):
        # L'admin a réduit la durée à 6 mois.
        AppSetting.objects.update_or_create(
            cle="epargne.contract_months", defaults={"valeur": "6"}
        )
        acc = _make_account(active_member, date(2026, 1, 15))

        call_command("backfill_refonte2026", stdout=StringIO())

        acc.refresh_from_db()
        # 15/01/2026 + 6 mois = 15/07/2026.
        assert acc.date_prochaine_maturite == date(2026, 7, 15)

    def test_end_of_month_clamps_to_last_valid_day(self, active_member):
        """Compte ouvert le 31/01 → maturité = 31/01 + 12 mois.
        Mais aussi protège contre les bugs +1 mois (28-jours).
        """
        # 6 mois après 31/01/2026 = 31/07/2026 (juillet a 31 jours, OK).
        AppSetting.objects.update_or_create(
            cle="epargne.contract_months", defaults={"valeur": "1"}
        )
        acc = _make_account(active_member, date(2026, 1, 31))

        call_command("backfill_refonte2026", stdout=StringIO())

        acc.refresh_from_db()
        # 31/01/2026 + 1 mois = 28/02/2026 (clamping mois court).
        assert acc.date_prochaine_maturite == date(2026, 2, 28)
