"""Tests du retrait sur l'**épargne classique** (part libre) — bug Sinora.

Contexte : une membre a de l'argent en épargne classique mais était bloquée
au retrait parce que le flow ne lisait que le solde de *collecte journalière*
(``SavingsAccount``), à zéro. La refonte ajoute le discriminant ``source`` :

  • ``source=CLASSIQUE_LIBRE`` → retrait sur ``ClassicSavingsAccount``, plafonné
    à ``solde_libre`` (= solde total − placements encore actifs). Le placement
    (tranches DISPONIBLE/ENGAGEE) reste bloqué car il garantit le funding crédit.

Couvre : disponibilité correcte, plafond = part libre, débit à l'approbation
sur le bon compte + transaction classique, garde placement, endpoint HTTP.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
    WithdrawalRequest,
)
from apps_coop.savings.services import decide_withdrawal, request_withdrawal


pytestmark = pytest.mark.django_db(transaction=True)


def _classic(member, solde):
    """Crée le compte épargne classique du membre avec un solde donné."""
    return ClassicSavingsAccount.objects.create(
        member=member,
        solde=Decimal(solde),
        date_ouverture=date(2026, 1, 1),
    )


def _place(member, montant, statut=LenderTranche.Statut.DISPONIBLE):
    """Fige une tranche placement (rend `montant` non-retirable)."""
    return LenderTranche.objects.create(
        member=member, montant=Decimal(montant), statut=statut,
    )


class TestRequestWithdrawalClassique:
    def test_libre_equals_solde_when_no_placement(self, active_member):
        """Sans placement : toute l'épargne classique est retirable."""
        cacc = _classic(active_member, "80000")
        wr = request_withdrawal(
            montant=Decimal("50000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        assert wr.statut == WithdrawalRequest.Statut.EN_ATTENTE
        assert wr.source == WithdrawalRequest.Source.CLASSIQUE_LIBRE
        assert wr.classic_account_id == cacc.id
        assert wr.account_id is None

    def test_placement_reduces_available(self, active_member):
        """Le placement actif (DISPONIBLE ou ENGAGEE) est retranché du dispo."""
        cacc = _classic(active_member, "80000")
        _place(active_member, "30000", LenderTranche.Statut.DISPONIBLE)
        _place(active_member, "10000", LenderTranche.Statut.ENGAGEE)
        # solde_libre = 80000 − 40000 = 40000 → 45000 doit être refusé
        with pytest.raises(ValueError, match="(?i)supérieur au solde"):
            request_withdrawal(
                montant=Decimal("45000"),
                source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
                classic_account=cacc,
            )

    def test_placement_libere_does_not_block(self, active_member):
        """Une tranche LIBEREE/ANNULEE ne bloque plus rien."""
        cacc = _classic(active_member, "50000")
        _place(active_member, "20000", LenderTranche.Statut.LIBEREE)
        _place(active_member, "5000", LenderTranche.Statut.ANNULEE)
        wr = request_withdrawal(
            montant=Decimal("50000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        assert wr.montant == Decimal("50000")

    def test_pending_scoped_per_account(self, active_member):
        """Un pending classique n'empêche pas un pending collecte (comptes distincts)."""
        cacc = _classic(active_member, "50000")
        request_withdrawal(
            montant=Decimal("10000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        # 2e demande classique en attente → refus
        with pytest.raises(ValueError, match="(?i)déjà en attente"):
            request_withdrawal(
                montant=Decimal("5000"),
                source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
                classic_account=cacc,
            )
        # mais une demande collecte reste possible
        acc = active_member.savings_account
        acc.solde = Decimal("20000")
        acc.save(update_fields=["solde"])
        wr2 = request_withdrawal(acc, montant=Decimal("5000"))
        assert wr2.source == WithdrawalRequest.Source.COLLECTE


class TestDecideWithdrawalClassique:
    def test_approve_debits_classic_account_only(self, active_member, admin_user):
        cacc = _classic(active_member, "80000")
        _place(active_member, "30000")  # 30k bloqué en placement
        wr = request_withdrawal(
            montant=Decimal("40000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        decide_withdrawal(wr, decided_by=admin_user, approve=True)

        wr.refresh_from_db()
        cacc.refresh_from_db()
        assert wr.statut == WithdrawalRequest.Statut.APPROUVEE
        # Solde classique débité, la collecte reste intacte
        assert cacc.solde == Decimal("40000.00")
        assert active_member.savings_account.solde == Decimal("0.00")
        # Transaction classique de type RETRAIT créée et liée
        assert wr.classic_transaction_id is not None
        ctx = ClassicSavingsTransaction.objects.get(pk=wr.classic_transaction_id)
        assert ctx.type_op == ClassicSavingsTransaction.TypeOp.RETRAIT
        assert ctx.montant == Decimal("40000")
        assert ctx.solde_apres == Decimal("40000.00")
        # Placement toujours actif (garantie funding préservée)
        assert cacc.solde_placement_actif == Decimal("30000")

    def test_approve_guards_placement_at_decision(self, active_member, admin_user):
        """Si un placement est créé APRÈS la demande, l'approbation refuse
        d'entamer la part désormais bloquée."""
        cacc = _classic(active_member, "50000")
        wr = request_withdrawal(
            montant=Decimal("50000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        # Le membre place 20k entre-temps → solde_libre tombe à 30k
        _place(active_member, "20000")
        with pytest.raises(ValueError, match="(?i)solde retirable insuffisant"):
            decide_withdrawal(wr, decided_by=admin_user, approve=True)
        cacc.refresh_from_db()
        assert cacc.solde == Decimal("50000")  # inchangé


class TestClassiqueEndpoint:
    def test_member_creates_classique_withdrawal_via_api(
        self, client, active_member, admin_user
    ):
        _classic(active_member, "60000")
        client.force_login(active_member.user)
        r = client.post(
            "/api/v1/savings/withdrawal/",
            data={
                "montant": "25000",
                "motif": "Frais santé",
                "source": "classique_libre",
                "mode_paiement": "presentiel",
            },
            content_type="application/json",
        )
        assert r.status_code == 201, r.content
        body = r.json()
        assert body["source"] == "classique_libre"
        wid = body["id"]

        client.force_login(admin_user)
        rd = client.post(
            f"/api/v1/admin/withdrawals/{wid}/decide/",
            data={"decision": "approuvee"},
            content_type="application/json",
        )
        assert rd.status_code == 200, rd.content
        active_member.classic_savings_account.refresh_from_db()
        assert active_member.classic_savings_account.solde == Decimal("35000.00")

    def test_classique_withdrawal_appears_in_my_withdrawals(
        self, client, active_member
    ):
        cacc = _classic(active_member, "40000")
        request_withdrawal(
            montant=Decimal("10000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            classic_account=cacc,
        )
        client.force_login(active_member.user)
        r = client.get("/api/v1/savings/withdrawals/me/")
        assert r.status_code == 200, r.content
        items = r.json()
        rows = items["results"] if isinstance(items, dict) else items
        assert any(row["source"] == "classique_libre" for row in rows)
