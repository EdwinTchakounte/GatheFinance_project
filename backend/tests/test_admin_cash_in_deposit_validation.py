"""Versement manuel agence (`POST /payments/admin/cash-in/`) — le cash-in admin
applique désormais les MÊMES règles de versement que le canal membre.

Avant le fix 2026-07-21, ce endpoint créait des dépôts SANS validation :
  * R1 — collecte : ni pas de 50 FCFA, ni minimum/jour ;
  * R2 — classique : ni gate `config.actif`, ni plancher 1 000, ni plafond ;
  * R3 — classique : `is_placement=True` accepté hors fenêtre → écriture marquée
    « placement » sans tranche prêteur (argent NON gelé mais annoncé comme placé).

Ces tests figent l'alignement sur `apps_coop/payments/deposit_validation.py`.

R3 a changé de forme en 2026-10 : le placement hors fenêtre n'est plus refusé
à l'admin, il est ASSUMÉ. Ce qu'il fallait éviter — une écriture « placement »
sans tranche — est désormais évité par l'autre bout : le hook crée la tranche
quand `Payment.placement_force_admin` est posé. Voir `TestR3PlacementWindow`.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AppSetting
from apps_coop.savings.models import (
    ClassicSavingsConfig,
    ClassicSavingsTransaction,
    SavingsTransaction,
)


pytestmark = pytest.mark.django_db

CASH_IN = "/api/v1/payments/admin/cash-in/"


def _admin_client(admin_user) -> APIClient:
    c = APIClient()
    c.force_authenticate(admin_user)
    return c


def _post(client, member, **body):
    return client.post(CASH_IN, {"member_id": member.id, **body}, format="json")


# ---------------------------------------------------------------------------
# R1 — collecte : pas de 50 FCFA + minimum/jour
# ---------------------------------------------------------------------------
class TestR1CollecteAmountRules:
    def test_non_multiple_of_step_rejected(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="1037")
        assert r.status_code == 400, r.content
        assert b"multiple" in r.content
        assert not SavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_below_min_per_day_rejected(self, active_member, admin_user):
        # 950 est multiple de 50 mais < 1 000/jour → refus.
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="950")
        assert r.status_code == 400, r.content
        assert not SavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_valid_collecte_accepted(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne", montant="1000")
        assert r.status_code == 201, r.content
        assert SavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=SavingsTransaction.TypeOp.DEPOT,
        ).count() == 1


# ---------------------------------------------------------------------------
# R2 — classique : gate config.actif + plancher 1 000 + plafond
# ---------------------------------------------------------------------------
class TestR2ClassiqueAmountRules:
    def test_below_floor_rejected(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="500")
        assert r.status_code == 400, r.content
        assert b"minimum" in r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_closed_product_rejected(self, active_member, admin_user):
        cfg = ClassicSavingsConfig.get_solo()
        cfg.actif = False
        cfg.save(update_fields=["actif"])
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="5000")
        assert r.status_code == 400, r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_above_max_rejected(self, active_member, admin_user):
        cfg = ClassicSavingsConfig.get_solo()
        cfg.actif = True
        cfg.depot_max = 100000
        cfg.save(update_fields=["actif", "depot_max"])
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="200000")
        assert r.status_code == 400, r.content
        assert not ClassicSavingsTransaction.objects.filter(account__member=active_member).exists()

    def test_valid_classique_accepted(self, active_member, admin_user):
        r = _post(_admin_client(admin_user), active_member, type="epargne_classique", montant="5000")
        assert r.status_code == 201, r.content
        assert ClassicSavingsTransaction.objects.filter(
            account__member=active_member,
            type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        ).count() == 1


# ---------------------------------------------------------------------------
# R3 — placement hors fenêtre refusé (pas d'écriture « placement » sans tranche)
# ---------------------------------------------------------------------------
class TestRemboursementGuards:
    """BUG-1/BUG-2 — le cash-in remboursement admin doit refuser un crédit non
    remboursable et un trop-perçu, comme le canal membre (sinon argent perdu)."""

    def test_over_payment_rejected(self, active_member, admin_user):
        from apps_coop.loans.models import Loan
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        assert loan.statut == Loan.Statut.ACTIF
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant=str(int(loan.solde_restant) + 5000),
        )
        assert r.status_code == 400, r.content
        assert b"solde restant" in r.content

    def test_closed_loan_rejected(self, active_member, admin_user):
        from apps_coop.loans.models import Loan
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        loan.statut = Loan.Statut.CLOTURE
        loan.save(update_fields=["statut"])
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant="1000",
        )
        assert r.status_code == 400, r.content

    def test_valid_repayment_accepted(self, active_member, admin_user):
        from tests.test_loan_note_pdf_ch9 import _build_lr

        _, loan = _build_lr(active_member, with_loan=True)
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="remboursement",
            loan_id=loan.id,
            montant="1000",
        )
        assert r.status_code == 201, r.content


class TestR3PlacementWindow:
    """Dérogation admin au placement (2026-10).

    L'admin encaisse au guichet, devant le membre. Lui refuser le placement
    parce que la date-limite est passée ou que le membre a dépassé sa fenêtre
    d'ancienneté l'obligeait à verser en LIBRE puis à rattraper autrement.

    Le risque que la barrière d'origine évitait — une écriture marquée
    « placement » sans tranche prêteur en face, donc de l'argent annoncé comme
    gelé qui ne l'est pas — est désormais traité à la source : le cash-in pose
    `placement_force_admin`, et le hook crée la tranche sur ce signal.

    Le canal MEMBRE n'est pas touché : `init_payment` refuse toujours
    (cf. `tests/test_placement_window.py`).
    """

    def _close_placement(self):
        AppSetting.objects.update_or_create(
            cle="epargne.placement.enabled",
            defaults={"valeur": "false", "description": ""},
        )

    def test_admin_peut_placer_meme_placement_ferme(self, active_member, admin_user):
        self._close_placement()

        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        assert r.status_code == 201, r.content
        tx = ClassicSavingsTransaction.objects.get(account__member=active_member)
        assert tx.is_placement is True

    def test_la_tranche_preteur_est_bien_creee(self, active_member, admin_user):
        """Le point entier de la dérogation : sans tranche, l'argent ne serait
        pas gelé alors que l'écriture le proclamerait."""
        from apps_coop.savings.models import LenderTranche

        self._close_placement()

        _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        tranches = LenderTranche.objects.filter(member=active_member)
        assert tranches.count() == 1
        assert tranches.first().montant == Decimal("5000")

    def test_la_derogation_est_marquee_sur_le_paiement(self, active_member, admin_user):
        from apps_coop.payments.models import Payment

        self._close_placement()

        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        payment = Payment.objects.get(pk=r.json()["id"])
        assert payment.placement_force_admin is True

    def test_un_placement_dans_les_clous_n_est_pas_marque(self, active_member, admin_user):
        """Placement ouvert et membre éligible : rien d'exceptionnel, donc pas
        de marqueur — sinon le journal se remplirait de fausses dérogations.

        Il faut rouvrir explicitement le placement : la date-limite par défaut
        (2026-08-01) est dépassée, donc à ce jour TOUT placement admin serait
        marqué comme dérogation.
        """
        from apps_coop.payments.models import Payment

        AppSetting.objects.update_or_create(
            cle="savings.placement.closed_from",
            defaults={"valeur": "2099-01-01", "description": ""},
        )
        AppSetting.objects.update_or_create(
            cle="epargne.placement.eligibility_months",
            defaults={"valeur": "0", "description": ""},
        )

        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        assert r.status_code == 201, r.content
        payment = Payment.objects.get(pk=r.json()["id"])
        assert payment.placement_force_admin is False

    def test_la_derogation_est_tracee_dans_l_audit(self, active_member, admin_user):
        from apps_coop.audit.models import AuditLog

        self._close_placement()

        _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        log = AuditLog.objects.filter(action="payment.cash_in_admin").latest("id")
        assert log.details_json["placement_force_admin"] is True

    def test_hors_fenetre_d_anciennete_aussi(self, active_member, admin_user):
        """L'autre verrou : le membre a dépassé ses N premiers mois."""
        from apps_coop.payments.models import Payment

        AppSetting.objects.update_or_create(
            cle="epargne.placement.eligibility_months",
            defaults={"valeur": "0", "description": ""},
        )
        AppSetting.objects.update_or_create(
            cle="epargne.placement.eligibility_months",
            defaults={"valeur": "1", "description": ""},
        )
        active_member.date_adhesion = date.today() - timedelta(days=400)
        active_member.save(update_fields=["date_adhesion"])

        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=True,
        )

        assert r.status_code == 201, r.content
        assert Payment.objects.get(pk=r.json()["id"]).placement_force_admin is True

    def test_libre_still_accepted_when_placement_closed(self, active_member, admin_user):
        AppSetting.objects.update_or_create(
            cle="epargne.placement.enabled",
            defaults={"valeur": "false", "description": ""},
        )
        # Même produit fermé au placement, un dépôt LIBRE passe.
        r = _post(
            _admin_client(admin_user),
            active_member,
            type="epargne_classique",
            montant="5000",
            is_placement=False,
        )
        assert r.status_code == 201, r.content
        tx = ClassicSavingsTransaction.objects.get(account__member=active_member)
        assert tx.is_placement is False
