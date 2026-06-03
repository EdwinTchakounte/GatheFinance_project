"""LOT 2 (refonte 2026) — Fondations data model pour la séparation 3 produits.

Couvre :
  - Champs ajoutés sur ``SavingsAccount`` (end_of_month_preference)
  - Champs ajoutés sur ``SavingsTransaction`` (nb_jours_couverts, 3 nouveaux TypeOp)
  - Champs ajoutés sur ``ClassicSavingsAccount`` (maturité + statut renouvellement)
  - Champs ajoutés sur ``ClassicSavingsTransaction`` (2 nouveaux TypeOp)
  - Champ ajouté sur ``Payment`` (nb_jours_couverts)
  - AppSettings 2026 seedés avec les bons défauts

Aucun business logic — les crons et services 2026 viennent en LOT 4-6.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.audit.services import get_int_setting, get_str_setting
from apps_coop.payments.models import Payment
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# SavingsAccount (= Collecte journalière 2026)
# ---------------------------------------------------------------------------


class TestSavingsAccountEndOfMonthPreference:

    def test_default_is_cash(self, active_member):
        acc = active_member.savings_account
        # Les comptes existants ont le défaut Django (cash).
        assert acc.end_of_month_preference == "cash"

    def test_member_can_switch_to_epargne(self, active_member):
        acc = active_member.savings_account
        acc.end_of_month_preference = (
            SavingsAccount.EndOfMonthPreference.EPARGNE
        )
        acc.save(update_fields=["end_of_month_preference"])
        acc.refresh_from_db()
        assert acc.end_of_month_preference == "epargne"

    def test_choices_are_locked(self):
        choices = dict(SavingsAccount.EndOfMonthPreference.choices)
        assert set(choices.keys()) == {"cash", "epargne"}


# ---------------------------------------------------------------------------
# SavingsTransaction — multi-jours + nouveaux TypeOp
# ---------------------------------------------------------------------------


class TestSavingsTransactionNbJoursCouverts:

    def test_default_nb_jours_is_one(self, active_member):
        # Crée une transaction de dépôt classique (1 jour).
        tx = SavingsTransaction.objects.create(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.DEPOT,
            montant=Decimal("1000"),
            solde_apres=Decimal("1000"),
            date=timezone.now(),
        )
        assert tx.nb_jours_couverts == 1

    def test_multi_day_prepayment(self, active_member):
        # 5000 FCFA pour 5 jours.
        tx = SavingsTransaction.objects.create(
            account=active_member.savings_account,
            type_op=SavingsTransaction.TypeOp.DEPOT,
            montant=Decimal("5000"),
            solde_apres=Decimal("5000"),
            date=timezone.now(),
            nb_jours_couverts=5,
        )
        assert tx.nb_jours_couverts == 5


class TestSavingsTransactionNewTypeOps:
    """Les nouveaux TypeOp 2026 doivent exister et être persistables."""

    @pytest.mark.parametrize(
        "type_op_value,expected_label_fragment",
        [
            ("commission", "Commission"),
            ("restitution_cash", "Restitution"),
            ("bascule_epargne", "Bascule"),
            ("retrait_force", "Prélèvement forcé"),  # déjà LOT 1 contentieux
        ],
    )
    def test_new_typeop_persists(
        self, active_member, type_op_value, expected_label_fragment
    ):
        tx = SavingsTransaction.objects.create(
            account=active_member.savings_account,
            type_op=type_op_value,
            montant=Decimal("100"),
            solde_apres=Decimal("0"),
            date=timezone.now(),
        )
        tx.refresh_from_db()
        assert tx.type_op == type_op_value
        # Le display label de l'enum doit contenir le mot attendu.
        assert expected_label_fragment in tx.get_type_op_display()


# ---------------------------------------------------------------------------
# ClassicSavingsAccount — maturité 1 an + state machine renouvellement
# ---------------------------------------------------------------------------


class TestClassicSavingsAccountMaturity:

    def test_defaults_on_new_account(self, active_member):
        acc = ClassicSavingsAccount.objects.create(
            member=active_member,
            solde=Decimal("0"),
            date_ouverture=date.today(),
        )
        # Champs LOT 2 — défauts attendus.
        assert acc.date_prochaine_maturite is None
        assert acc.cycle_courant == 1
        assert acc.statut_renouvellement == "actif"

    def test_state_machine_choices(self):
        statuts = dict(
            ClassicSavingsAccount.StatutRenouvellement.choices
        )
        assert set(statuts.keys()) == {
            "actif",
            "notifie",
            "urgence",
            "en_attente_paiement",
            "archive",
        }

    def test_cycle_increments_on_renewal(self, active_member):
        acc = ClassicSavingsAccount.objects.create(
            member=active_member,
            solde=Decimal("0"),
            date_ouverture=date.today(),
        )
        # Simule un renouvellement réussi (LOT 5 fera ça automatiquement).
        acc.cycle_courant += 1
        acc.statut_renouvellement = (
            ClassicSavingsAccount.StatutRenouvellement.ACTIF
        )
        acc.save()
        assert acc.cycle_courant == 2


# ---------------------------------------------------------------------------
# ClassicSavingsTransaction — 2 nouveaux TypeOp pour anniversaire
# ---------------------------------------------------------------------------


class TestClassicSavingsTransactionNewTypeOps:

    def test_restitution_maturite_persists(self, active_member):
        acc = ClassicSavingsAccount.objects.create(
            member=active_member,
            solde=Decimal("100000"),
            date_ouverture=date.today(),
        )
        tx = ClassicSavingsTransaction.objects.create(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_MATURITE,
            montant=Decimal("100000"),
            solde_apres=Decimal("0"),
            date=timezone.now(),
        )
        assert tx.type_op == "restitution_maturite"
        assert "Restitution" in tx.get_type_op_display()

    def test_frais_renouvellement_persists(self, active_member):
        acc = ClassicSavingsAccount.objects.create(
            member=active_member,
            solde=Decimal("0"),
            date_ouverture=date.today(),
        )
        tx = ClassicSavingsTransaction.objects.create(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.FRAIS_RENOUVELLEMENT,
            montant=Decimal("5000"),
            solde_apres=Decimal("0"),
            date=timezone.now(),
        )
        assert tx.type_op == "frais_renouvellement"
        assert "Frais" in tx.get_type_op_display()


# ---------------------------------------------------------------------------
# Payment.nb_jours_couverts
# ---------------------------------------------------------------------------


class TestPaymentNbJoursCouverts:

    def test_default_is_one(self, active_member):
        payment = Payment.objects.create(
            member=active_member,
            montant=Decimal("1000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.EN_ATTENTE,
            date_versement=timezone.now(),
        )
        assert payment.nb_jours_couverts == 1

    def test_multi_day_at_payment_level(self, active_member):
        payment = Payment.objects.create(
            member=active_member,
            montant=Decimal("5000"),
            type=Payment.Type.EPARGNE,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.EN_ATTENTE,
            date_versement=timezone.now(),
            nb_jours_couverts=5,
        )
        assert payment.nb_jours_couverts == 5


# ---------------------------------------------------------------------------
# Seed AppSettings — défauts LOT 2 corrects et idempotents
# ---------------------------------------------------------------------------


class TestAppSettingsLot2Seed:
    """Le seed crée les clés LOT 2 avec les bons défauts métier."""

    @pytest.fixture(autouse=True)
    def _clean_settings(self):
        AppSetting.objects.filter(
            cle__in=[
                "collecte.min_per_day",
                "collecte.prepay.max_days",
                "collecte.monthly.default_action",
                "epargne.contract_months",
                "epargne.renewal_fee",
                "epargne.renewal_grace_days",
            ]
        ).delete()

    def test_seed_creates_lot2_keys(self):
        call_command("seed_app_settings")
        assert get_int_setting("collecte.min_per_day", 0) == 1000
        assert get_int_setting("collecte.prepay.max_days", 0) == 30
        assert get_str_setting("collecte.monthly.default_action", "") == "cash"
        assert get_int_setting("epargne.contract_months", 0) == 12
        assert get_int_setting("epargne.renewal_fee", 0) == 5000
        assert get_int_setting("epargne.renewal_grace_days", 0) == 30

    def test_seed_idempotent_does_not_overwrite_admin_edit(self):
        # 1er seed → valeurs par défaut.
        call_command("seed_app_settings")
        # Admin édite (relève le minimum journalier à 1500).
        AppSetting.objects.filter(cle="collecte.min_per_day").update(
            valeur="1500"
        )
        # 2ᵉ seed → la valeur admin DOIT être préservée.
        call_command("seed_app_settings")
        assert get_int_setting("collecte.min_per_day", 0) == 1500
