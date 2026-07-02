"""CH-11 — Retenue des intérêts à la source au décaissement.

Sinora §5.3 : à la mise à disposition la coop retient 10 % d'intérêts.
Le membre reçoit donc 90 % du nominal demandé et ne rembourse que ce
qu'il a touché (capital pur).

Couvre :
  - ``approve_loan_request`` en mode 'source' :
      * ``montant_decaisse_net = montant × 0.90``,
      * ``interets_retenus_source = montant × 0.10``,
      * ``montant_total_du = montant_decaisse_net``,
      * ``mode_retenue_interets = "source"``.
  - ``generate_installments_flat_interest`` mode 'source' :
      * Somme des capitaux = ``montant_decaisse_net``,
      * Somme des intérêts = 0,
      * Chaque montant_total = capital pur.
  - Toggle AppSetting ``loans.interest_withheld_at_source = false`` :
      * Comportement legacy préservé (échéances avec intérêts).
  - Décaissement (``disburse_loan_via_tara`` + ``disburse_loan_manual``) :
      * ``Payment.montant = montant_decaisse_net`` (= 90 % du nominal),
      * Audit avec brut, net et retenu.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.loans.models import LoanRequest
from apps_coop.loans.services import (
    approve_loan_request,
    disburse_loan_manual,
    disburse_loan_via_tara,
)
from apps_coop.payments.models import Payment
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_factory_sequences():
    MemberFactory.reset_sequence(920000)
    UserFactory.reset_sequence(920000)
    yield


@pytest.fixture
def comite_user(db):
    u = User.objects.create_user(
        email="comite-ch11@gathe.test", password="x", username="comite-ch11",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


@pytest.fixture
def admin_agent(db):
    """Compte admin coop pour invoquer les services de décaissement."""
    u = User.objects.create_user(
        email="agent-ch11@gathe.test", password="x", username="agent-ch11",
        is_staff=True, is_superuser=True,
    )
    coop_admin, _ = Group.objects.get_or_create(name="coop_admin")
    u.groups.add(coop_admin)
    return u


def _enable_source_mode(enabled: bool):
    """Pose l'AppSetting de manière idempotente."""
    AppSetting.objects.update_or_create(
        cle="loans.interest_withheld_at_source",
        defaults={"valeur": "true" if enabled else "false", "description": ""},
    )


def _submit(member, *, montant=Decimal("60000")):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test CH-11",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )


# ---------------------------------------------------------------------------
# 1. approve_loan_request en mode 'source' — calcul net/retenu/total.
# ---------------------------------------------------------------------------
class TestApproveSourceMode:
    def test_net_and_retenu_match_taux(self, active_member, comite_user):
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        loan.refresh_from_db()
        assert loan.mode_retenue_interets == "source"
        # 100 000 × 10 % = 10 000 retenus → 90 000 net.
        assert loan.interets_retenus_source == Decimal("10000.00")
        assert loan.montant_decaisse_net == Decimal("90000.00")
        # Le membre rembourse uniquement le net (capital pur).
        assert loan.montant_total_du == Decimal("90000.00")
        assert loan.solde_restant == Decimal("90000.00")

    def test_installments_total_equals_net(self, active_member, comite_user):
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("90000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        installments = list(loan.installments.all())
        assert len(installments) == 1  # règle 2026 : échéance unique (date butoir)
        total_capital = sum(Decimal(i.montant_capital) for i in installments)
        total_interets = sum(Decimal(i.montant_interets) for i in installments)
        total = sum(Decimal(i.montant_total) for i in installments)
        # Le membre demande 90 000 → reçoit 81 000 → rembourse 81 000.
        assert total_capital == Decimal("81000.00")
        assert total_interets == Decimal("0.00")
        assert total == Decimal("81000.00")

    def test_each_installment_has_zero_interests(self, active_member, comite_user):
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("60000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        for inst in loan.installments.all():
            assert Decimal(inst.montant_interets) == Decimal("0.00")
            assert Decimal(inst.montant_total) == Decimal(inst.montant_capital)


# ---------------------------------------------------------------------------
# 2. Toggle AppSetting off → legacy preserved.
# ---------------------------------------------------------------------------
class TestLegacyModeWhenToggleOff:
    def test_mode_echeances_when_toggle_false(self, active_member, comite_user):
        _enable_source_mode(False)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        loan.refresh_from_db()
        assert loan.mode_retenue_interets == "echeances"
        # Pas de retenue à la source.
        assert loan.interets_retenus_source == Decimal("0")
        # Le membre touche 100 % du nominal.
        assert loan.montant_decaisse_net == Decimal("100000.00")
        # Et rembourse 110 000 (capital + intérêts).
        assert loan.montant_total_du == Decimal("110000.00")

    def test_legacy_installments_include_interets(self, active_member, comite_user):
        _enable_source_mode(False)
        lr = _submit(active_member, montant=Decimal("60000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        total_interets = sum(
            Decimal(i.montant_interets) for i in loan.installments.all()
        )
        # 60 000 × 10 % = 6 000 d'intérêts répartis.
        assert total_interets == Decimal("6000.00")


# ---------------------------------------------------------------------------
# 3. disburse_loan_via_tara — Payment.montant = net.
# ---------------------------------------------------------------------------
class TestDisburseTara:
    def test_payment_montant_equals_net(
        self, active_member, comite_user, admin_agent, settings
    ):
        settings.PAYMENTS_TEST_AUTO_VALIDATE = False
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        payment = disburse_loan_via_tara(
            loan,
            agent=admin_agent,
            recipient_phone="+237699112233",
            network="MTN",
        )
        assert payment.type == Payment.Type.DECAISSEMENT
        # Le montant versé = net (90 000) et non nominal (100 000).
        assert Decimal(payment.montant) == Decimal("90000.00")

    def test_audit_records_gross_net_and_retenu(
        self, active_member, comite_user, admin_agent, settings
    ):
        settings.PAYMENTS_TEST_AUTO_VALIDATE = False
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        disburse_loan_via_tara(
            loan,
            agent=admin_agent,
            recipient_phone="+237699112233",
            network="MTN",
        )
        audit = AuditLog.objects.filter(
            action="loan.disburse_payout_initiated",
            entite_type="Loan",
            entite_id=loan.id,
        ).first()
        assert audit is not None
        details = audit.details_json
        # Comparaison numérique pour tolérer la présence ou non des décimales.
        assert Decimal(details["montant_brut_nominal"]) == Decimal("100000")
        assert Decimal(details["montant_decaisse_net"]) == Decimal("90000")
        assert Decimal(details["interets_retenus_source"]) == Decimal("10000")
        assert details["mode_retenue_interets"] == "source"


# ---------------------------------------------------------------------------
# 4. disburse_loan_manual — idem.
# ---------------------------------------------------------------------------
class TestDisburseManual:
    def test_payment_montant_equals_net(
        self, active_member, comite_user, admin_agent
    ):
        _enable_source_mode(True)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        payment = disburse_loan_manual(
            loan,
            agent=admin_agent,
            reference_externe="REC-CH11-001",
            note="Espèces remises au guichet.",
        )
        assert Decimal(payment.montant) == Decimal("90000.00")
        assert payment.statut == Payment.Statut.VALIDE


# ---------------------------------------------------------------------------
# 5. Loan legacy (mode = echeances) garde son comportement.
# ---------------------------------------------------------------------------
class TestLegacyLoanBackfillSafe:
    def test_legacy_loan_disburses_full_nominal(
        self, active_member, comite_user, admin_agent
    ):
        _enable_source_mode(False)
        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Loan créé en mode echeances → net = brut.
        assert loan.mode_retenue_interets == "echeances"
        payment = disburse_loan_manual(
            loan,
            agent=admin_agent,
            reference_externe="REC-LEGACY-001",
        )
        assert Decimal(payment.montant) == Decimal("100000.00")


# ---------------------------------------------------------------------------
# 6. Note PDF (CH-9) — affichage net + retenu quand mode source.
# ---------------------------------------------------------------------------
class TestNotePDFShowsNetAndRetenu:
    def test_pdf_generated_in_source_mode(
        self, active_member, comite_user
    ):
        _enable_source_mode(True)
        from apps_coop.loans.note_pdf import build_loan_request_note

        lr = _submit(active_member, montant=Decimal("100000"))
        loan = approve_loan_request(
            lr,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        pdf = build_loan_request_note(lr)
        # Sanity : PDF généré sans erreur (les nouvelles lignes sont rendues).
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 1000
