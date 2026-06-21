"""LOT 5 (refonte 2026) — Cron quotidien anniversaire épargne classique.

Couvre :
  - State machine ACTIF → NOTIFIE → URGENCE → EN_ATTENTE_PAIEMENT → ARCHIVE
  - Restitution intégrale à J0 + ligne ledger RESTITUTION_MATURITE
  - Idempotence (pas 2× restitution même cycle)
  - Service ``renew_classic_savings_account`` : cycle++, nouvelle maturité,
    ACTIF, ligne FRAIS_RENOUVELLEMENT, audit
  - Refus de renouvellement si ARCHIVE
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
)
from apps_coop.savings.services import renew_classic_savings_account
from apps_coop.savings.tasks import epargne_anniversary_processing


pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_classic(
    member,
    *,
    maturite: date,
    solde: Decimal = Decimal("100000"),
    cycle: int = 1,
    statut=None,
):
    """Helper — crée un ClassicSavingsAccount paramétré."""
    if statut is None:
        statut = ClassicSavingsAccount.StatutRenouvellement.ACTIF
    return ClassicSavingsAccount.objects.create(
        member=member,
        solde=solde,
        date_ouverture=date.today() - timedelta(days=365),
        date_prochaine_maturite=maturite,
        cycle_courant=cycle,
        statut_renouvellement=statut,
    )


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


class TestStateMachine:
    """Le cron transitionne le statut selon ``days_until_maturity``."""

    def test_30_or_more_days_stays_actif(self, active_member):
        acc = _make_classic(active_member, maturite=date.today() + timedelta(days=60))
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "actif"

    def test_29_days_transitions_to_notifie(self, active_member):
        acc = _make_classic(active_member, maturite=date.today() + timedelta(days=15))
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "notifie"

    def test_3_days_transitions_to_urgence(self, active_member):
        acc = _make_classic(active_member, maturite=date.today() + timedelta(days=3))
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "urgence"

    def test_j0_triggers_restitution_and_en_attente(self, active_member):
        acc = _make_classic(
            active_member,
            maturite=date.today(),
            solde=Decimal("100000"),
        )
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "en_attente_paiement"
        assert acc.solde == Decimal("0")
        # La restitution est tracée dans le ledger.
        tx = ClassicSavingsTransaction.objects.get(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_MATURITE,
        )
        assert tx.montant == Decimal("100000")
        assert tx.solde_apres == Decimal("0")

    def test_within_grace_stays_en_attente(self, active_member):
        # Maturité passée de 10 jours (grace 30j par défaut).
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=10),
            solde=Decimal("0"),  # déjà restitué
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "en_attente_paiement"

    def test_grace_exceeded_transitions_to_archive(self, active_member):
        # Maturité passée de 31 jours (au-delà de la grace 30j).
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=31),
            solde=Decimal("0"),
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "archive"

    def test_archive_excluded_from_processing(self, active_member):
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=100),
            statut=ClassicSavingsAccount.StatutRenouvellement.ARCHIVE,
        )
        summary = epargne_anniversary_processing()
        # Le compte archivé n'est pas processé.
        acc.refresh_from_db()
        assert acc.statut_renouvellement == "archive"


# ---------------------------------------------------------------------------
# Idempotence restitution
# ---------------------------------------------------------------------------


class TestRestitutionIdempotence:
    """La restitution n'arrive qu'une fois par cycle."""

    def test_second_run_does_not_double_restitution(self, active_member):
        acc = _make_classic(
            active_member,
            maturite=date.today(),
            solde=Decimal("100000"),
        )
        epargne_anniversary_processing()
        epargne_anniversary_processing()

        restitutions = ClassicSavingsTransaction.objects.filter(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_MATURITE,
        )
        assert restitutions.count() == 1


# ---------------------------------------------------------------------------
# Service renew_classic_savings_account
# ---------------------------------------------------------------------------


class TestRenewService:

    def test_renewal_advances_cycle_and_resets_status(
        self, active_member, admin_user
    ):
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=5),
            solde=Decimal("0"),
            cycle=1,
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        renew_classic_savings_account(account=acc, paid_by=admin_user)

        acc.refresh_from_db()
        assert acc.cycle_courant == 2
        assert acc.statut_renouvellement == "actif"
        # Nouvelle maturité = today + 12 mois (par défaut).
        assert acc.date_prochaine_maturite > date.today() + timedelta(days=350)
        assert acc.date_prochaine_maturite < date.today() + timedelta(days=380)

    def test_renewal_creates_frais_renouvellement_ledger(
        self, active_member, admin_user
    ):
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=5),
            solde=Decimal("0"),
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        renew_classic_savings_account(account=acc, paid_by=admin_user)

        tx = ClassicSavingsTransaction.objects.get(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.FRAIS_RENOUVELLEMENT,
        )
        # Frais par défaut = 5000.
        assert tx.montant == Decimal("5000")

    def test_renewal_respects_appsetting_fee(self, active_member, admin_user):
        AppSetting.objects.update_or_create(
            cle="epargne.renewal_fee", defaults={"valeur": "8000"}
        )
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=5),
            solde=Decimal("0"),
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        renew_classic_savings_account(account=acc, paid_by=admin_user)

        tx = ClassicSavingsTransaction.objects.get(
            account=acc,
            type_op=ClassicSavingsTransaction.TypeOp.FRAIS_RENOUVELLEMENT,
        )
        assert tx.montant == Decimal("8000")

    def test_renewal_writes_audit(self, active_member, admin_user):
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=5),
            statut=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
        )
        renew_classic_savings_account(account=acc, paid_by=admin_user)

        audit = AuditLog.objects.filter(action="savings.renewed").first()
        assert audit is not None
        assert audit.details_json["new_cycle"] == 2
        assert audit.user == admin_user

    def test_renewal_refused_on_archive(self, active_member, admin_user):
        acc = _make_classic(
            active_member,
            maturite=date.today() - timedelta(days=100),
            statut=ClassicSavingsAccount.StatutRenouvellement.ARCHIVE,
        )
        with pytest.raises(ValueError, match="archivé"):
            renew_classic_savings_account(account=acc, paid_by=admin_user)


# ---------------------------------------------------------------------------
# Flow complet — état de l'art réaliste
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    """Restitution → en attente → renouvellement → ACTIF nouveau cycle."""

    def test_full_renewal_cycle(self, active_member, admin_user):
        # Compte à J0.
        acc = _make_classic(
            active_member,
            maturite=date.today(),
            solde=Decimal("250000"),
            cycle=1,
        )

        # Le cron quotidien tourne — restitution + EN_ATTENTE_PAIEMENT.
        epargne_anniversary_processing()
        acc.refresh_from_db()
        assert acc.solde == Decimal("0")
        assert acc.statut_renouvellement == "en_attente_paiement"

        # Quelques jours après, le membre revient et paie ses frais.
        renew_classic_savings_account(account=acc, paid_by=admin_user)
        acc.refresh_from_db()
        assert acc.cycle_courant == 2
        assert acc.statut_renouvellement == "actif"
