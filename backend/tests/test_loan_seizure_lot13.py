"""Tests LOT 13 — Saisie multi-source R1 étendue (refonte 2026 §9.2).

Couvre les nouveautés vs. R1 legacy 2025 :
  * **Q5** : ``LenderTranche.ENGAGEE`` exclues du débit épargne classique.
  * **§9.2** : avaliste inclus si ``LoanRequest.avaliste`` posé.
  * Ordre des sources admin-configurable.
  * Kill-switches ``include_avaliste`` et ``exclude_engaged_tranches``.
  * Breakdown legs[] dans le résultat (audit + diagnostic).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.seizure_services import seize_for_loan
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
    SavingsAccount,
    SavingsTransaction,
)

from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setting(key: str, value: str):
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": value})


def _build_classique(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member,
        solde=Decimal(solde),
        date_ouverture=date.today(),
    )


def _set_collecte(member, solde):
    SavingsAccount.objects.filter(member=member).update(solde=Decimal(solde))


def _build_loan_with_avaliste(borrower, *, avaliste=None, solde_restant=200000):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=Decimal("200000"),
        duree_mois=3,
        motif="Saisie test",
        statut=LoanRequest.Statut.APPROUVEE,
        avaliste=avaliste,
    )
    return Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier=f"LOT13-{borrower.numero_membre}-{solde_restant}",
        montant=Decimal("200000"),
        taux_interet=Decimal("0.10"),
        taux_penalite=Decimal("0.50"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=90),
        date_premiere_echeance=date.today() - timedelta(days=80),
        montant_total_du=Decimal("220000"),
        solde_restant=Decimal(solde_restant),
        statut=Loan.Statut.CONTENTIEUX,
    )


# ---------------------------------------------------------------------------
# Q5 — exclusion LenderTranche.ENGAGEE
# ---------------------------------------------------------------------------


class TestExcludeEngagedTranches:
    def test_engaged_tranche_excluded_from_classique(self):
        m = MemberFactory()
        _build_classique(m, 100000)
        # 60k engagés sur un autre crédit → saisissable = 40k
        LenderTranche.objects.create(
            member=m,
            montant=Decimal("60000"),
            statut=LenderTranche.Statut.ENGAGEE,
        )
        loan = _build_loan_with_avaliste(m, solde_restant=100000)
        result = seize_for_loan(loan)
        # Saisie classique limitée à 40k (60k protégés Q5).
        assert result.saisie_borrower == Decimal("40000")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("60000")
        assert loan.poursuite_judiciaire_at is not None

    def test_disponible_tranche_not_excluded(self):
        m = MemberFactory()
        _build_classique(m, 100000)
        # Une tranche DISPONIBLE n'est pas un engagement actif → ne protège rien.
        LenderTranche.objects.create(
            member=m,
            montant=Decimal("60000"),
            statut=LenderTranche.Statut.DISPONIBLE,
        )
        loan = _build_loan_with_avaliste(m, solde_restant=100000)
        result = seize_for_loan(loan)
        assert result.saisie_borrower == Decimal("100000")

    def test_kill_switch_disables_exclusion(self):
        _setting("loans.seizure.exclude_engaged_tranches", "false")
        m = MemberFactory()
        _build_classique(m, 100000)
        LenderTranche.objects.create(
            member=m,
            montant=Decimal("60000"),
            statut=LenderTranche.Statut.ENGAGEE,
        )
        loan = _build_loan_with_avaliste(m, solde_restant=100000)
        result = seize_for_loan(loan)
        # Protection désactivée → toute l'épargne classique saisie.
        assert result.saisie_borrower == Decimal("100000")


# ---------------------------------------------------------------------------
# §9.2 — saisie avaliste
# ---------------------------------------------------------------------------


class TestAvalisteSaisie:
    def test_avaliste_savings_seized_after_borrower(self):
        borrower = MemberFactory()
        _set_collecte(borrower, 50000)
        avaliste = MemberFactory()
        _build_classique(avaliste, 200000)
        loan = _build_loan_with_avaliste(
            borrower, avaliste=avaliste, solde_restant=200000
        )
        result = seize_for_loan(loan)
        # Borrower contribue 50k (collecte), avaliste 150k (classique) =
        # total 200k → dette épongée.
        assert result.saisie_borrower == Decimal("50000")
        assert result.saisie_avaliste == Decimal("150000")
        assert result.solde_restant_apres == Decimal("0")
        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CLOTURE
        # Une transaction ledger pour le compte avaliste classique.
        avaliste.refresh_from_db()
        avaliste_tx = ClassicSavingsTransaction.objects.filter(
            account=avaliste.classic_savings_account
        )
        assert avaliste_tx.count() == 1
        assert avaliste_tx.first().type_op == ClassicSavingsTransaction.TypeOp.RETRAIT_FORCE

    def test_no_avaliste_keeps_legacy_behavior(self):
        borrower = MemberFactory()
        _set_collecte(borrower, 100000)
        loan = _build_loan_with_avaliste(borrower, solde_restant=200000)
        result = seize_for_loan(loan)
        assert result.saisie_avaliste == Decimal("0")
        assert result.saisie_borrower == Decimal("100000")
        assert result.solde_restant_apres == Decimal("100000")
        assert result.poursuite_engagee is True

    def test_kill_switch_disables_avaliste(self):
        _setting("loans.seizure.include_avaliste", "false")
        borrower = MemberFactory()
        _set_collecte(borrower, 50000)
        avaliste = MemberFactory()
        _build_classique(avaliste, 500000)
        loan = _build_loan_with_avaliste(
            borrower, avaliste=avaliste, solde_restant=200000
        )
        result = seize_for_loan(loan)
        # Avaliste ignoré → seul borrower contribue.
        assert result.saisie_avaliste == Decimal("0")
        assert result.saisie_borrower == Decimal("50000")
        assert result.poursuite_engagee is True

    def test_avaliste_collecte_also_seized(self):
        borrower = MemberFactory()
        avaliste = MemberFactory()
        _set_collecte(avaliste, 80000)
        loan = _build_loan_with_avaliste(
            borrower, avaliste=avaliste, solde_restant=100000
        )
        result = seize_for_loan(loan)
        # Borrower n'a rien, avaliste collecte 80k → reliquat 20k → poursuite.
        assert result.saisie_avaliste == Decimal("80000")
        assert result.solde_restant_apres == Decimal("20000")
        assert result.poursuite_engagee is True


# ---------------------------------------------------------------------------
# Ordre source — admin tunable
# ---------------------------------------------------------------------------


class TestSourceOrder:
    def test_default_borrower_classique_first(self):
        m = MemberFactory()
        _build_classique(m, 30000)
        _set_collecte(m, 30000)
        loan = _build_loan_with_avaliste(m, solde_restant=40000)
        result = seize_for_loan(loan)
        # 30k pris sur classique d'abord, 10k restant sur collecte.
        legs = {leg.source: leg.montant for leg in result.legs}
        assert legs["borrower_classique"] == Decimal("30000")
        assert legs["borrower_collecte"] == Decimal("10000")

    def test_admin_promotes_collecte_first(self):
        _setting(
            "loans.seizure.source_order",
            "borrower_collecte,borrower_classique",
        )
        m = MemberFactory()
        _build_classique(m, 30000)
        _set_collecte(m, 30000)
        loan = _build_loan_with_avaliste(m, solde_restant=40000)
        result = seize_for_loan(loan)
        legs = {leg.source: leg.montant for leg in result.legs}
        assert legs["borrower_collecte"] == Decimal("30000")
        assert legs["borrower_classique"] == Decimal("10000")

    def test_source_omitted_is_skipped(self):
        # Ordre ne mentionne PAS borrower_classique → elle est ignorée.
        _setting(
            "loans.seizure.source_order", "borrower_collecte"
        )
        m = MemberFactory()
        _build_classique(m, 200000)
        _set_collecte(m, 30000)
        loan = _build_loan_with_avaliste(m, solde_restant=100000)
        result = seize_for_loan(loan)
        assert result.saisie_borrower == Decimal("30000")
        # Classique intacte.
        m.refresh_from_db()
        assert Decimal(m.classic_savings_account.solde) == Decimal("200000")

    def test_malformed_order_falls_back_default(self):
        _setting("loans.seizure.source_order", "bogus,,xxx")
        m = MemberFactory()
        _set_collecte(m, 30000)
        loan = _build_loan_with_avaliste(m, solde_restant=30000)
        result = seize_for_loan(loan)
        assert result.saisie_borrower == Decimal("30000")


# ---------------------------------------------------------------------------
# Audit + legs[] + summary dict
# ---------------------------------------------------------------------------


class TestSummaryAndAudit:
    def test_summary_dict_legacy_compat(self):
        m = MemberFactory()
        _set_collecte(m, 100000)
        loan = _build_loan_with_avaliste(m, solde_restant=80000)
        result = seize_for_loan(loan)
        summary = result.to_summary()
        # Clés legacy
        assert "saisie" in summary
        assert "epargne_apres" in summary
        assert "solde_restant_apres" in summary
        assert "poursuite" in summary
        # Nouvelles clés
        assert "saisie_borrower" in summary
        assert "saisie_avaliste" in summary
        assert "legs" in summary
        assert any(leg["source"] == "borrower_collecte" for leg in summary["legs"])

    def test_audit_records_breakdown(self):
        borrower = MemberFactory()
        _set_collecte(borrower, 30000)
        avaliste = MemberFactory()
        _build_classique(avaliste, 70000)
        loan = _build_loan_with_avaliste(
            borrower, avaliste=avaliste, solde_restant=100000
        )
        seize_for_loan(loan)
        log = AuditLog.objects.filter(
            action="loan.savings_seized", entite_id=loan.id
        ).first()
        assert log is not None
        assert log.details_json["saisie_borrower"] == "30000.00"
        assert log.details_json["saisie_avaliste"] == "70000.00"
        assert log.details_json["avaliste_member_id"] == avaliste.id
        assert len(log.details_json["legs"]) >= 2

    def test_idempotent_second_call(self):
        m = MemberFactory()
        _set_collecte(m, 100000)
        loan = _build_loan_with_avaliste(m, solde_restant=50000)
        first = seize_for_loan(loan)
        assert first.saisie_borrower == Decimal("50000")
        second = seize_for_loan(loan)
        assert second.no_op is True
        # Pas de double ledger row.
        assert SavingsTransaction.objects.filter(
            account__member=m,
            type_op=SavingsTransaction.TypeOp.RETRAIT_FORCE,
        ).count() == 1
