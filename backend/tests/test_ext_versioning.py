"""EXT-versioning — Taux de pénalité figé sur le crédit au décaissement.

Prouve qu'un changement de ``RateParam.LATE_PENALTY`` par l'admin n'affecte
PAS les crédits déjà décaissés (juridiquement, le membre signe un contrat
avec un taux donné).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.tasks import suivi_retards_quotidien
from apps_coop.payments.models import RateParam


pytestmark = pytest.mark.django_db(transaction=True)


def _build_loan(member, *, taux_penalite, numero="GF-CR-VER"):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="EXT-versioning test",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=numero,
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        taux_penalite=taux_penalite,
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=120),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("110000"),
        statut=Loan.Statut.ACTIF,
    )


def _build_overdue_installment(loan):
    return LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=1,
        date_echeance=date.today() - timedelta(days=10),
        montant_capital=Decimal("33334"),
        montant_interets=Decimal("3333"),  # 50% × 3333 = 1666.50 si taux=0.50
        montant_total=Decimal("36667"),
        montant_paye=Decimal("0"),
        statut=LoanInstallment.Statut.A_VENIR,
    )


@pytest.fixture
def enable_art12():
    """Active la pénalité Art.12 par échéance (désactivée par défaut en 2026)."""
    from apps_coop.audit.models import AppSetting
    AppSetting.objects.update_or_create(
        cle="loans.penalite_par_echeance.enabled",
        defaults={"valeur": "true"},
    )


class TestPenaltyRateIsFrozenOnLoan:
    """Le crédit applique SON taux figé, pas le taux global courant."""

    def test_existing_loan_keeps_its_old_penalty_rate(self, active_member, enable_art12):
        """Loan créé à 50 % ; admin passe le taux global à 80 % ; la pénalité
        appliquée à ce crédit doit rester calculée à 50 %.
        """
        # 1) Crédit figé à 50 %.
        loan = _build_loan(active_member, taux_penalite=Decimal("0.50"))
        _build_overdue_installment(loan)

        # 2) L'admin change le taux global à 80 %.
        RateParam.objects.create(
            code=RateParam.Code.LATE_PENALTY,
            libelle="Pénalité",
            valeur=Decimal("0.80"),
            actif=True,
        )

        # 3) Le cron passe — la pénalité doit utiliser 50 % (taux figé), pas 80 %.
        suivi_retards_quotidien()

        inst = LoanInstallment.objects.get(loan=loan)
        # 3333 × 50 % = 1 666.50 (pas 2 666.40)
        assert inst.montant_penalite == Decimal("1666.50")

    def test_new_loan_uses_current_global_rate(self, active_member, enable_art12):
        """Les FUTURS crédits, eux, prennent bien le nouveau taux."""
        # Admin a déjà passé le taux global à 80 %.
        RateParam.objects.create(
            code=RateParam.Code.LATE_PENALTY,
            libelle="Pénalité",
            valeur=Decimal("0.80"),
            actif=True,
        )
        # Un crédit décaissé MAINTENANT prend 80 % (simulé : taux figé = 0.80).
        loan_new = _build_loan(
            active_member,
            taux_penalite=Decimal("0.80"),
            numero="GF-CR-VER-NEW",
        )
        _build_overdue_installment(loan_new)

        suivi_retards_quotidien()

        inst = LoanInstallment.objects.get(loan=loan_new)
        # 3333 × 80 % = 2 666.40
        assert inst.montant_penalite == Decimal("2666.40")

    def test_legacy_loan_with_null_falls_back_to_global(self, active_member, enable_art12):
        """Crédit legacy (avant EXT-versioning, ``taux_penalite=NULL``)
        → fallback sur le taux global courant (rétrocompat)."""
        # taux_penalite=None pour simuler un crédit pré-EXT-versioning.
        loan = _build_loan(
            active_member,
            taux_penalite=None,
            numero="GF-CR-VER-LEGACY",
        )
        _build_overdue_installment(loan)

        # Taux global = défaut Règlement (0.50).
        suivi_retards_quotidien()

        inst = LoanInstallment.objects.get(loan=loan)
        # Pas d'override DB → 0.50 → 1 666.50
        assert inst.montant_penalite == Decimal("1666.50")
