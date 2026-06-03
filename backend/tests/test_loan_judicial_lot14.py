"""Tests LOT 14 — Escalade judiciaire phase D/E (refonte 2026 §9.3-9.4).

Couvre :
  * ``open_judicial_escalation`` + guards (poursuite_judiciaire_at posé, reliquat > 0, idempotent).
  * ``record_judicial_decision`` (EN_INSTANCE → DECISION_RENDUE).
  * ``record_judicial_execution`` (DECISION_RENDUE → EXECUTEE, décrément solde, clôture loan).
  * ``classer_sans_suite`` (abandon admin).
  * ``auto_escalate_eligible_loans`` (cron : mode manual no-op, auto déclenche, délai respecté).
  * AppSettings + cron schedule seedés.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.loans.judicial_services import (
    auto_escalate_eligible_loans,
    classer_sans_suite,
    open_judicial_escalation,
    record_judicial_decision,
    record_judicial_execution,
)
from apps_coop.loans.models import JudicialEscalation, Loan, LoanRequest

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setting(key: str, value: str):
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": value})


def _build_loan_with_pursuit(
    *,
    member=None,
    solde_restant=Decimal("50000"),
    poursuite_days_ago=70,
):
    """Crée un Loan en contentieux avec poursuite_judiciaire_at posée."""
    m = member or MemberFactory()
    lr = LoanRequest.objects.create(
        member=m,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test escalade",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        member=m,
        loan_request=lr,
        numero_dossier=f"LOT14-{m.numero_membre}-{solde_restant}",
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        taux_penalite=Decimal("0.50"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=poursuite_days_ago + 30),
        date_premiere_echeance=date.today() - timedelta(days=poursuite_days_ago + 20),
        montant_total_du=Decimal("110000"),
        solde_restant=solde_restant,
        statut=Loan.Statut.CONTENTIEUX,
        epargne_saisie_at=timezone.now() - timedelta(days=poursuite_days_ago + 1),
        epargne_saisie_montant=Decimal("60000"),
        poursuite_judiciaire_at=timezone.now() - timedelta(days=poursuite_days_ago),
    )
    return loan


# ---------------------------------------------------------------------------
# open_judicial_escalation
# ---------------------------------------------------------------------------


class TestOpen:
    def test_creates_in_instance(self):
        loan = _build_loan_with_pursuit()
        admin = UserFactory(is_staff=True)
        esc = open_judicial_escalation(
            loan,
            motif="Mise en demeure restée sans réponse.",
            declenche_par=admin,
            mode="manual",
        )
        assert esc.statut == JudicialEscalation.Statut.EN_INSTANCE
        assert esc.declenche_par == admin
        assert esc.declenche_mode == "manual"
        assert esc.loan_id == loan.id

    def test_idempotent_returns_existing(self):
        loan = _build_loan_with_pursuit()
        first = open_judicial_escalation(
            loan, motif="A", declenche_par=UserFactory()
        )
        second = open_judicial_escalation(
            loan, motif="B (sera ignoré)", declenche_par=UserFactory()
        )
        assert first.pk == second.pk
        assert JudicialEscalation.objects.filter(loan=loan).count() == 1

    def test_guard_requires_poursuite(self):
        m = MemberFactory()
        lr = LoanRequest.objects.create(
            member=m,
            montant_demande=Decimal("100000"),
            duree_mois=3,
            motif="test",
            statut=LoanRequest.Statut.APPROUVEE,
        )
        # Loan sans poursuite_judiciaire_at posé
        loan = Loan.objects.create(
            member=m,
            loan_request=lr,
            numero_dossier="LOT14-NOPURSUIT",
            montant=Decimal("100000"),
            taux_interet=Decimal("0.10"),
            taux_penalite=Decimal("0.50"),
            duree_mois=3,
            date_decaissement=date.today() - timedelta(days=100),
            date_premiere_echeance=date.today() - timedelta(days=90),
            montant_total_du=Decimal("110000"),
            solde_restant=Decimal("50000"),
            statut=Loan.Statut.ACTIF,
        )
        with pytest.raises(ValueError, match="poursuite"):
            open_judicial_escalation(loan, motif="test")

    def test_guard_requires_reliquat(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("0"))
        with pytest.raises(ValueError, match="reliquat"):
            open_judicial_escalation(loan, motif="test")

    def test_audit_recorded(self):
        loan = _build_loan_with_pursuit()
        open_judicial_escalation(loan, motif="test motif")
        log = AuditLog.objects.filter(
            action="loan.judicial_escalation_opened", entite_id=loan.id
        ).first()
        assert log is not None
        assert log.details_json["solde_restant"] == "50000.00"


# ---------------------------------------------------------------------------
# record_judicial_decision
# ---------------------------------------------------------------------------


class TestDecision:
    def test_transitions_to_decision_rendue(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        biens = [
            {"description": "Mobylette", "valeur_estimee": "120000"},
            {"description": "Frigo", "valeur_estimee": "80000"},
        ]
        result = record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=biens
        )
        assert result.statut == JudicialEscalation.Statut.DECISION_RENDUE
        assert result.decision_date == date.today()
        assert len(result.biens_saisissables) == 2

    def test_idempotent_already_decision_rendue(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        first = record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        # Deuxième appel — no-op, pas d'écrasement.
        second = record_judicial_decision(
            first, decision_date=date(2099, 1, 1), biens_saisissables=["x"]
        )
        assert second.decision_date == first.decision_date
        assert second.biens_saisissables == []

    def test_rejects_from_wrong_state(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        # Classer puis tenter une décision
        classer_sans_suite(esc, motif="irrecouvrable")
        esc.refresh_from_db()
        with pytest.raises(ValueError, match="Transition impossible"):
            record_judicial_decision(
                esc, decision_date=date.today(), biens_saisissables=[]
            )


# ---------------------------------------------------------------------------
# record_judicial_execution
# ---------------------------------------------------------------------------


class TestExecution:
    def test_decrements_solde_and_closes_loan_when_fully_recovered(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("50000"))
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        result = record_judicial_execution(
            esc,
            execution_date=date.today(),
            montant_recouvre=Decimal("50000"),
            biens_saisis=[{"description": "Mobylette", "valeur_realisee": "50000"}],
        )
        assert result.statut == JudicialEscalation.Statut.EXECUTEE
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0")
        assert loan.statut == Loan.Statut.CLOTURE

    def test_partial_recovery_keeps_loan_open(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("100000"))
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        record_judicial_execution(
            esc,
            execution_date=date.today(),
            montant_recouvre=Decimal("30000"),
            biens_saisis=[],
        )
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("70000")
        assert loan.statut == Loan.Statut.CONTENTIEUX  # toujours ouvert

    def test_clamps_overshoot(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("50000"))
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        # On déclare 80k recouvrés mais reliquat = 50k → clamp.
        result = record_judicial_execution(
            esc,
            execution_date=date.today(),
            montant_recouvre=Decimal("80000"),
            biens_saisis=[],
        )
        assert result.montant_recouvre == Decimal("50000")
        loan.refresh_from_db()
        assert loan.solde_restant == Decimal("0")

    def test_idempotent_when_already_executed(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("50000"))
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        first = record_judicial_execution(
            esc, execution_date=date.today(), montant_recouvre=Decimal("50000")
        )
        second = record_judicial_execution(
            first,
            execution_date=date(2099, 1, 1),
            montant_recouvre=Decimal("99999"),
        )
        assert second.execution_date == first.execution_date
        assert second.montant_recouvre == first.montant_recouvre

    def test_rejects_negative_amount(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        with pytest.raises(ValueError, match="négatif"):
            record_judicial_execution(
                esc,
                execution_date=date.today(),
                montant_recouvre=Decimal("-1"),
            )

    def test_rejects_from_en_instance(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        # Pas de décision posée → exec doit refuser.
        with pytest.raises(ValueError, match="Transition impossible"):
            record_judicial_execution(
                esc,
                execution_date=date.today(),
                montant_recouvre=Decimal("10000"),
            )

    def test_audit_recorded(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        record_judicial_execution(
            esc,
            execution_date=date.today(),
            montant_recouvre=Decimal("50000"),
        )
        log = AuditLog.objects.filter(
            action="loan.biens_seized", entite_id=loan.id
        ).first()
        assert log is not None
        assert Decimal(log.details_json["montant_recouvre"]) == Decimal("50000")


# ---------------------------------------------------------------------------
# classer_sans_suite
# ---------------------------------------------------------------------------


class TestClasserSansSuite:
    def test_classes_from_en_instance(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        result = classer_sans_suite(esc, motif="Débiteur introuvable.")
        assert result.statut == JudicialEscalation.Statut.CLASSEE_SANS_SUITE
        assert result.closed_at is not None
        assert result.close_reason == "irrecouvrable"
        assert "Débiteur introuvable" in result.motif

    def test_idempotent(self):
        loan = _build_loan_with_pursuit()
        esc = open_judicial_escalation(loan, motif="test")
        first = classer_sans_suite(esc, motif="m1")
        second = classer_sans_suite(esc, motif="m2 — sera ignoré")
        assert first.closed_at == second.closed_at

    def test_rejects_from_executee(self):
        loan = _build_loan_with_pursuit(solde_restant=Decimal("50000"))
        esc = open_judicial_escalation(loan, motif="test")
        record_judicial_decision(
            esc, decision_date=date.today(), biens_saisissables=[]
        )
        record_judicial_execution(
            esc, execution_date=date.today(), montant_recouvre=Decimal("50000")
        )
        with pytest.raises(ValueError, match="Transition impossible"):
            classer_sans_suite(esc, motif="trop tard")


# ---------------------------------------------------------------------------
# Cron — auto_escalate_eligible_loans
# ---------------------------------------------------------------------------


class TestAutoEscalate:
    def test_manual_mode_is_noop(self):
        loan = _build_loan_with_pursuit()
        result = auto_escalate_eligible_loans()
        assert result["mode"] == "manual"
        assert result["opened"] == 0
        assert not JudicialEscalation.objects.filter(loan=loan).exists()

    def test_auto_mode_opens(self):
        _setting("loans.judicial_escalation.mode", "auto")
        _setting("loans.judicial_escalation.delay_days", "60")
        loan = _build_loan_with_pursuit(poursuite_days_ago=70)
        result = auto_escalate_eligible_loans()
        assert result["mode"] == "auto"
        assert result["opened"] == 1
        esc = JudicialEscalation.objects.get(loan=loan)
        assert esc.declenche_mode == "auto"
        assert esc.declenche_par is None

    def test_auto_mode_respects_delay(self):
        _setting("loans.judicial_escalation.mode", "auto")
        _setting("loans.judicial_escalation.delay_days", "60")
        # Loan dont la poursuite n'a que 10 jours — délai non atteint.
        _build_loan_with_pursuit(poursuite_days_ago=10)
        result = auto_escalate_eligible_loans()
        assert result["opened"] == 0

    def test_auto_mode_skips_loans_with_existing_escalation(self):
        _setting("loans.judicial_escalation.mode", "auto")
        loan = _build_loan_with_pursuit(poursuite_days_ago=70)
        open_judicial_escalation(loan, motif="pré-existant", declenche_par=UserFactory())
        result = auto_escalate_eligible_loans()
        assert result["opened"] == 0
        assert JudicialEscalation.objects.filter(loan=loan).count() == 1

    def test_hybrid_mode_also_opens(self):
        _setting("loans.judicial_escalation.mode", "hybrid")
        _setting("loans.judicial_escalation.delay_days", "60")
        loan = _build_loan_with_pursuit(poursuite_days_ago=70)
        result = auto_escalate_eligible_loans()
        assert result["mode"] == "hybrid"
        assert result["opened"] == 1
        esc = JudicialEscalation.objects.get(loan=loan)
        assert esc.declenche_mode == "hybrid"

    def test_task_wrapper_returns_counters(self):
        from apps_coop.loans.tasks import judicial_auto_escalation_task

        _setting("loans.judicial_escalation.mode", "auto")
        _build_loan_with_pursuit(poursuite_days_ago=70)
        result = judicial_auto_escalation_task()
        assert "opened" in result
        assert result["opened"] >= 1


# ---------------------------------------------------------------------------
# AppSettings + cron schedule seeded
# ---------------------------------------------------------------------------


class TestSeed:
    def test_seed_creates_lot14_keys(self):
        from django.core.management import call_command

        call_command("seed_app_settings")
        for key in [
            "loans.judicial_escalation.mode",
            "loans.judicial_escalation.delay_days",
            "loans.judicial_escalation.notify_before_days",
        ]:
            assert AppSetting.objects.filter(cle=key).exists(), f"missing {key}"

    def test_cron_schedule_seeded(self):
        from django.core.management import call_command
        from django_q.models import Schedule

        call_command("seed_q_schedules")
        sched = Schedule.objects.filter(name="loans.judicial.auto_escalate")
        assert sched.exists()
        assert (
            sched.first().func
            == "apps_coop.loans.tasks.judicial_auto_escalation_task"
        )
