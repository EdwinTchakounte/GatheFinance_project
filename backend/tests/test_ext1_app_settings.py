"""EXT-1 — Tunables admin via ``AppSetting``.

Prouve qu'un admin peut modifier des paramètres (seuil de contentieux, cut-off
horaire, durée de reconduction, lead-days du rappel) **sans déploiement**, et
que le système retombe sur les défauts réglementaires si la table n'est pas
seedée ou si la valeur est invalide.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.audit.services import get_int_setting, get_str_setting
from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.tasks import (
    CONTENTIEUX_THRESHOLD_DAYS,
    DUE_SOON_LEAD_DAYS,
    rappel_echeances_proches,
    suivi_retards_quotidien,
)
from apps_coop.savings.cutoff import (
    COLLECTION_LOCATION,
    DAILY_CUTOFF_HOUR,
    compute_value_date,
    get_collection_location,
)


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers (unit) — comportement déterministe sans toucher la DB métier.
# ---------------------------------------------------------------------------

class TestGetIntSetting:
    def test_returns_default_when_key_missing(self):
        assert get_int_setting("inexistant.bidule", 42) == 42

    def test_returns_db_value_when_key_present(self):
        AppSetting.objects.create(cle="test.delai", valeur="7")
        assert get_int_setting("test.delai", 99) == 7

    def test_falls_back_when_value_non_numeric(self):
        # Si l'admin tape "abc" par erreur, on retombe sur le défaut.
        AppSetting.objects.create(cle="test.bad", valeur="abc")
        assert get_int_setting("test.bad", 5) == 5

    def test_falls_back_when_value_empty(self):
        AppSetting.objects.create(cle="test.empty", valeur="")
        assert get_int_setting("test.empty", 3) == 3


class TestGetStrSetting:
    def test_returns_default_when_key_missing(self):
        assert get_str_setting("inexistant.libelle", "défaut") == "défaut"

    def test_returns_db_value_when_key_present(self):
        AppSetting.objects.create(cle="test.lieu", valeur="Agence Bonapriso")
        assert get_str_setting("test.lieu", "défaut") == "Agence Bonapriso"


# ---------------------------------------------------------------------------
# Cut-off épargne — modifiable sans déploiement.
# ---------------------------------------------------------------------------

class TestCutoffHourTunable:
    """Admin tunable: ``savings.cutoff.hour``."""

    def test_default_cutoff_when_no_app_setting(self):
        # Un mercredi 16h00 → date du jour (avant 17h par défaut).
        wed_16h = datetime(2026, 5, 27, 16, 0)  # mercredi
        assert compute_value_date(wed_16h) == date(2026, 5, 27)

    def test_admin_can_advance_cutoff_to_15h(self):
        # Admin avance le cut-off à 15h00 — un dépôt à 16h passe à J+1.
        AppSetting.objects.create(cle="savings.cutoff.hour", valeur="15")
        wed_16h = datetime(2026, 5, 27, 16, 0)  # mercredi
        # J+1 ouvré = jeudi 28
        assert compute_value_date(wed_16h) == date(2026, 5, 28)

    def test_admin_can_push_cutoff_to_19h(self):
        # Admin pousse le cut-off à 19h — un dépôt à 17h30 reste au jour J.
        AppSetting.objects.create(cle="savings.cutoff.hour", valeur="19")
        wed_17h30 = datetime(2026, 5, 27, 17, 30)
        assert compute_value_date(wed_17h30) == date(2026, 5, 27)


class TestCollectionLocationTunable:
    def test_default_location_when_no_app_setting(self):
        assert get_collection_location() == COLLECTION_LOCATION

    def test_admin_can_change_agency_label(self):
        AppSetting.objects.create(
            cle="savings.collection_location",
            valeur="Agence Bonapriso — Rue de l'Hôtel de Ville",
        )
        assert get_collection_location().startswith("Agence Bonapriso")


# ---------------------------------------------------------------------------
# Cron retards & rappel J-N — modifiables sans déploiement (intégration).
# ---------------------------------------------------------------------------


def _build_loan(member, numero="GF-CR-EXT1"):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="EXT-1 test",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=numero,
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=120),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("110000"),
        statut=Loan.Statut.ACTIF,
    )


def _build_installment(loan, *, days_late, numero=1):
    return LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=numero,
        date_echeance=date.today() - timedelta(days=days_late),
        montant_capital=Decimal("33334"),
        montant_interets=Decimal("3333"),
        montant_total=Decimal("36667"),
        montant_paye=Decimal("0"),
        statut=LoanInstallment.Statut.A_VENIR,
    )


class TestContentieuxThresholdTunable:
    """Admin tunable: ``loans.contentieux.threshold_days``."""

    def test_admin_lowers_threshold_to_60_days(self, active_member):
        """À 60 jours, un retard de 70 jours bascule en CONTENTIEUX
        alors qu'avec le défaut réglementaire (90 jours) il resterait EN_RETARD.
        """
        AppSetting.objects.create(
            cle="loans.contentieux.threshold_days", valeur="60"
        )
        loan = _build_loan(active_member, numero="GF-CR-EXT1-CTX60")
        _build_installment(loan, days_late=70)  # > 60 mais < 90

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CONTENTIEUX

    def test_default_threshold_when_no_setting(self, active_member):
        """Sans AppSetting, retombe sur ``CONTENTIEUX_THRESHOLD_DAYS`` (90)."""
        loan = _build_loan(active_member, numero="GF-CR-EXT1-CTXDEF")
        # 70 jours < 90 : doit rester EN_RETARD, pas CONTENTIEUX.
        _build_installment(loan, days_late=70)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.EN_RETARD
        # Sanity check : le défaut hardcoded n'a pas dérivé.
        assert CONTENTIEUX_THRESHOLD_DAYS == 90


class TestDueSoonLeadDaysTunable:
    """Admin tunable: ``loans.due_soon.lead_days``."""

    def test_admin_extends_reminder_to_7_days(self, active_member):
        """Admin étend le rappel à J-7 — une échéance dans 7 jours déclenche."""
        from django.core.management import call_command
        call_command("seed_email_templates")

        AppSetting.objects.create(cle="loans.due_soon.lead_days", valeur="7")
        loan = _build_loan(active_member, numero="GF-CR-EXT1-SOON7")
        _build_installment(loan, days_late=-7)  # échéance dans 7 jours

        summary = rappel_echeances_proches()

        assert summary["rappels_envoyes"] == 1

    def test_default_lead_days_when_no_setting(self, active_member):
        """Sans AppSetting, retombe sur ``DUE_SOON_LEAD_DAYS`` (3)."""
        from django.core.management import call_command
        call_command("seed_email_templates")

        loan = _build_loan(active_member, numero="GF-CR-EXT1-SOONDEF")
        # Échéance dans 7 jours : hors fenêtre J-3 par défaut.
        _build_installment(loan, days_late=-7)

        summary = rappel_echeances_proches()

        assert summary["rappels_envoyes"] == 0
        assert DUE_SOON_LEAD_DAYS == 3
