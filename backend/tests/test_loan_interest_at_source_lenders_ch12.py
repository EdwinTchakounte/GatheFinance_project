"""CH-12 — Distribution immédiate des intérêts prêteurs (mode source).

Sinora §5.3 : en mode CH-11 "source", les intérêts sont retenus à la
mise à disposition. Pour que les prêteurs internes (LenderAllocation)
touchent leur part 50 %, on la distribue à T0 — pas au fil des
remboursements (le LOT 9 split est inopérant car aucune échéance ne
contient d'intérêt).

Couvre :
  - ``Loan.interest_share_rate_fige`` posé à l'approbation (snapshot
    de l'AppSetting ``lender.interest_share_rate``).
  - ``distribute_interest_share_at_source`` :
      * Crée 1 ``LenderInterestPayout`` par allocation, ``installment=None``.
      * Montants proportionnels à ``quote_part`` et résidu absorbé par la
        dernière allocation.
      * Crédite le ``ClassicSavingsAccount`` de chaque prêteur via une
        ``ClassicSavingsTransaction(INTERET_PRETEUR)``.
      * Cumule ``allocation.interest_share_paid_total``.
      * Idempotent : second appel = no-op.
      * Audit ``loan.interest_share_distributed_at_source`` posé.
  - No-op si :
      * Mode echeances (legacy CH-11),
      * Aucune ``LenderAllocation``,
      * ``share_rate_fige`` à 0 (kill-switch).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.loans.lender_payouts import distribute_interest_share_at_source
from apps_coop.loans.models import (
    LenderAllocation,
    LenderInterestPayout,
    Loan,
    LoanRequest,
)
from apps_coop.loans.services import approve_loan_request
from apps_coop.payments.models import Payment
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
)
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_factory_sequences():
    MemberFactory.reset_sequence(930000)
    UserFactory.reset_sequence(930000)
    yield


@pytest.fixture
def comite_user(db):
    u = User.objects.create_user(
        email="comite-ch12@gathe.test", password="x", username="comite-ch12",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _set_setting(key: str, value: str):
    AppSetting.objects.update_or_create(
        cle=key, defaults={"valeur": value, "description": ""}
    )


def _enable_source_mode(enabled: bool = True):
    _set_setting("loans.interest_withheld_at_source", "true" if enabled else "false")


def _set_share_rate(rate: str):
    _set_setting("lender.interest_share_rate", rate)


def _approve(member, comite_user, montant=Decimal("100000")):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test CH-12",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )
    return approve_loan_request(
        lr,
        decided_by=comite_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )


def _attach_lender(loan: Loan, lender, *, quote_part: Decimal):
    """Pose une LenderAllocation sur le Loan + assure un ClassicSavingsAccount."""
    montant_alloue = (Decimal(loan.montant) * quote_part).quantize(Decimal("0.01"))
    return LenderAllocation.objects.create(
        loan=loan,
        lender=lender,
        montant_alloue=montant_alloue,
        quote_part=quote_part,
    )


def _make_payment(loan):
    """Stub d'un Payment décaissement validé pour le test (pas de Tara)."""
    return Payment.objects.create(
        member=loan.member,
        montant=Decimal(loan.montant_decaisse_net or loan.montant),
        type=Payment.Type.DECAISSEMENT,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        provider_code="",
        validated_by=None,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
        loan=loan,
    )


# ---------------------------------------------------------------------------
# 1. Snapshot du taux à l'approbation.
# ---------------------------------------------------------------------------
class TestSnapshotShareRate:
    def test_share_rate_fige_at_approve(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.4")
        loan = _approve(active_member, comite_user)
        loan.refresh_from_db()
        assert loan.interest_share_rate_fige == Decimal("0.4000")

    def test_subsequent_setting_change_does_not_apply_retro(
        self, active_member, comite_user
    ):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        # On change l'AppSetting APRÈS l'approbation.
        _set_share_rate("0.9")
        loan.refresh_from_db()
        # Le Loan conserve la valeur figée.
        assert loan.interest_share_rate_fige == Decimal("0.5000")


# ---------------------------------------------------------------------------
# 2. Distribution à T0 — proportionnelle au quote_part.
# ---------------------------------------------------------------------------
class TestDistributionT0:
    def test_two_lenders_50_50_split(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        # 100 000 demandés → 10 000 retenus à la source.
        # Part prêteurs = 10 000 × 0.5 = 5 000 à se partager.
        assert loan.interets_retenus_source == Decimal("10000.00")

        l1 = MemberFactory()
        l2 = MemberFactory()
        _attach_lender(loan, l1, quote_part=Decimal("0.5"))
        _attach_lender(loan, l2, quote_part=Decimal("0.5"))

        payment = _make_payment(loan)
        payouts = distribute_interest_share_at_source(loan, payment)
        assert len(payouts) == 2
        # Chaque prêteur touche 2 500 (= 5 000 × 0.5).
        montants = sorted(Decimal(p.montant) for p in payouts)
        assert montants == [Decimal("2500.00"), Decimal("2500.00")]
        # installment=None car versement à T0.
        for p in payouts:
            assert p.installment is None
            assert p.payment_id == payment.id

    def test_proportional_to_quote_part(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        l1 = MemberFactory()
        l2 = MemberFactory()
        # 70 / 30 split.
        _attach_lender(loan, l1, quote_part=Decimal("0.7"))
        _attach_lender(loan, l2, quote_part=Decimal("0.3"))

        payment = _make_payment(loan)
        payouts = distribute_interest_share_at_source(loan, payment)
        assert len(payouts) == 2
        # 5 000 × 0.7 = 3 500, 5 000 × 0.3 = 1 500.
        by_lender = {p.allocation.lender_id: Decimal(p.montant) for p in payouts}
        assert by_lender[l1.id] == Decimal("3500.00")
        assert by_lender[l2.id] == Decimal("1500.00")

    def test_credits_lender_classic_savings(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        lender = MemberFactory()
        _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)

        distribute_interest_share_at_source(loan, payment)
        # ClassicSavingsAccount créé à la volée + crédité de 5 000.
        account = ClassicSavingsAccount.objects.get(member=lender)
        assert account.solde == Decimal("5000.00")
        # Une ClassicSavingsTransaction INTERET_PRETEUR créée.
        tx = ClassicSavingsTransaction.objects.get(
            account=account,
            type_op=ClassicSavingsTransaction.TypeOp.INTERET_PRETEUR,
        )
        assert tx.montant == Decimal("5000.00")
        assert tx.solde_apres == Decimal("5000.00")

    def test_cumulates_allocation_interest_share_paid_total(
        self, active_member, comite_user
    ):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        lender = MemberFactory()
        alloc = _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)

        distribute_interest_share_at_source(loan, payment)
        alloc.refresh_from_db()
        assert alloc.interest_share_paid_total == Decimal("5000.00")


# ---------------------------------------------------------------------------
# 3. Idempotence — second appel ne duplique pas.
# ---------------------------------------------------------------------------
class TestIdempotent:
    def test_second_call_returns_existing_payouts(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        lender = MemberFactory()
        _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)

        first = distribute_interest_share_at_source(loan, payment)
        second = distribute_interest_share_at_source(loan, payment)
        # Pas de nouveaux payouts créés au second appel.
        assert LenderInterestPayout.objects.filter(
            allocation__loan=loan, installment__isnull=True
        ).count() == 1
        assert len(first) == 1
        assert len(second) == 1
        # Le solde du prêteur reste à 5 000 (pas 10 000).
        account = ClassicSavingsAccount.objects.get(member=lender)
        assert account.solde == Decimal("5000.00")


# ---------------------------------------------------------------------------
# 4. No-op pour les cas legacy ou bloqués.
# ---------------------------------------------------------------------------
class TestNoopGuards:
    def test_no_payouts_in_echeances_mode(self, active_member, comite_user):
        _enable_source_mode(False)
        loan = _approve(active_member, comite_user)
        lender = MemberFactory()
        _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)
        assert loan.mode_retenue_interets == "echeances"
        payouts = distribute_interest_share_at_source(loan, payment)
        assert payouts == []
        assert not LenderInterestPayout.objects.filter(allocation__loan=loan).exists()

    def test_no_payouts_without_lenders(self, active_member, comite_user):
        _enable_source_mode(True)
        loan = _approve(active_member, comite_user)
        payment = _make_payment(loan)
        # Aucune LenderAllocation attachée.
        payouts = distribute_interest_share_at_source(loan, payment)
        assert payouts == []

    def test_kill_switch_share_rate_zero(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0")
        loan = _approve(active_member, comite_user)
        # Le loan est figé à 0 → distribution no-op même avec prêteurs.
        assert loan.interest_share_rate_fige == Decimal("0.0000")
        lender = MemberFactory()
        _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)
        payouts = distribute_interest_share_at_source(loan, payment)
        assert payouts == []


# ---------------------------------------------------------------------------
# 5. Audit.
# ---------------------------------------------------------------------------
class TestAudit:
    def test_audit_recorded(self, active_member, comite_user):
        _enable_source_mode(True)
        _set_share_rate("0.5")
        loan = _approve(active_member, comite_user)
        lender = MemberFactory()
        _attach_lender(loan, lender, quote_part=Decimal("1.0"))
        payment = _make_payment(loan)
        distribute_interest_share_at_source(loan, payment)

        audit = AuditLog.objects.filter(
            action="loan.interest_share_distributed_at_source",
            entite_type="Loan",
            entite_id=loan.id,
        ).first()
        assert audit is not None
        details = audit.details_json
        assert Decimal(details["interets_retenus_source"]) == Decimal("10000")
        assert Decimal(details["share_rate_fige"]) == Decimal("0.5")
        assert Decimal(details["pretteurs_total"]) == Decimal("5000")
        assert len(details["payouts"]) == 1
