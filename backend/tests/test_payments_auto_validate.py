"""Tests pour le mode `PAYMENTS_TEST_AUTO_VALIDATE`.

Ce flag, activé par env var en recette/staging, joue le webhook ``"valide"``
immédiatement après ``init_payin`` (et après ``init_payout`` côté retrait
MOMO). Le but : valider tous les flows métier sans dépendre de Tara live.

Couvre :
  - Off (défaut) → Payment reste EN_ATTENTE après init
  - On → Payment passe VALIDE + hook savings_deposit joué (solde crédité)
  - On + retrait MOMO → WithdrawalRequest COMPLETEE après decide(approve)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps_coop.payments.models import Payment


@pytest.fixture
def member_client(active_member):
    client = APIClient()
    client.force_authenticate(user=active_member.user)
    return client


@pytest.fixture
def init_payload():
    return {
        "type": "epargne",
        "montant": 1000,
        "phone": "+237699112233",
        "network": "MTN",
    }


# ---------------------------------------------------------------------------
# Comportement par défaut — flag OFF
# ---------------------------------------------------------------------------


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=False)
def test_off_payment_reste_en_attente(member_client, active_member, init_payload):
    res = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    assert res.status_code == 201
    pid = res.json()["payment"]["id"]
    payment = Payment.objects.get(pk=pid)
    assert payment.statut == Payment.Statut.EN_ATTENTE


# ---------------------------------------------------------------------------
# Flag ON — auto-validate
# ---------------------------------------------------------------------------


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_on_payment_passe_valide_et_solde_credite(
    member_client, active_member, init_payload
):
    solde_initial = active_member.savings_account.solde
    res = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    assert res.status_code == 201
    pid = res.json()["payment"]["id"]
    payment = Payment.objects.get(pk=pid)
    assert payment.statut == Payment.Statut.VALIDE
    # Hook savings_deposit a tourné — solde crédité.
    active_member.savings_account.refresh_from_db()
    assert active_member.savings_account.solde == solde_initial + Decimal("1000")


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_on_idempotent_si_relance(member_client, active_member, init_payload):
    """Deux init_payment distincts → 2 paiements validés, pas d'erreur."""
    r1 = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    r2 = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    assert r1.status_code == 201
    assert r2.status_code == 201
    # Le membre porte déjà un Payment frais_carnet (activation) → on ne compte
    # que les dépôts validés par les deux init.
    assert (
        Payment.objects.filter(member=active_member, statut=Payment.Statut.VALIDE)
        .exclude(type=Payment.Type.FRAIS_CARNET)
        .count()
        == 2
    )


# ---------------------------------------------------------------------------
# Retrait MOMO — payout auto-validé
# ---------------------------------------------------------------------------


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_retrait_momo_auto_complete(active_member, admin_user, tara_payout_on):
    """admin approve + flag ON → WR passe direct EN_PAYOUT puis COMPLETEE
    via le webhook DECAISSEMENT joué automatiquement."""
    from apps_coop.savings.services import decide_withdrawal, request_withdrawal
    from apps_coop.savings.models import WithdrawalRequest

    acc = active_member.savings_account
    acc.solde = Decimal("50000")
    acc.save(update_fields=["solde"])

    wr = request_withdrawal(
        acc,
        montant=Decimal("12000"),
        mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
        recipient_phone="690000099",
        network="MTN",
    )
    wr = decide_withdrawal(wr, approve=True, decided_by=admin_user)
    wr.refresh_from_db()
    assert wr.statut == WithdrawalRequest.Statut.COMPLETEE


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=False)
def test_retrait_momo_off_reste_en_payout(active_member, admin_user, tara_payout_on):
    """Sans flag, WR reste EN_PAYOUT (attente webhook Tara)."""
    from apps_coop.savings.services import decide_withdrawal, request_withdrawal
    from apps_coop.savings.models import WithdrawalRequest

    acc = active_member.savings_account
    acc.solde = Decimal("50000")
    acc.save(update_fields=["solde"])

    wr = request_withdrawal(
        acc,
        montant=Decimal("12000"),
        mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
        recipient_phone="690000099",
        network="MTN",
    )
    wr = decide_withdrawal(wr, approve=True, decided_by=admin_user)
    wr.refresh_from_db()
    assert wr.statut == WithdrawalRequest.Statut.EN_PAYOUT


# ---------------------------------------------------------------------------
# Décaissement crédit (Tara) — auto-validé
# ---------------------------------------------------------------------------


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_disburse_loan_via_tara_auto_active(active_member, admin_user):
    """Mode test ON → décaissement Tara joue immédiatement le webhook,
    le Loan bascule en `actif` avec `date_decaissement` fixée."""
    from datetime import date
    from apps_coop.loans.models import Loan, LoanRequest
    from apps_coop.loans.services import disburse_loan_via_tara
    from apps_coop.payments.models import Payment

    # LoanRequest préalable obligatoire (OneToOne PROTECT sur Loan).
    lr = LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=4,
        motif="Test décaissement auto",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    # Crée un Loan en attente de décaissement (pas encore actif).
    loan = Loan.objects.create(
        loan_request=lr,
        member=active_member,
        numero_dossier="GF-CR-TEST-001",
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=4,
        date_decaissement=date(2026, 1, 1),  # placeholder, sera réécrit par le hook
        date_premiere_echeance=date(2026, 2, 1),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("110000"),
        statut=Loan.Statut.ACTIF,
    )

    payment = disburse_loan_via_tara(
        loan,
        agent=admin_user,
        recipient_phone="690000077",
        network="MTN",
    )
    assert payment.statut == Payment.Statut.VALIDE
    # Idempotence : un seul Payment décaissement validé pour ce loan.
    assert (
        Payment.objects.filter(
            loan=loan, type=Payment.Type.DECAISSEMENT, statut=Payment.Statut.VALIDE
        ).count()
        == 1
    )


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=False)
def test_disburse_loan_via_tara_off_reste_en_attente(active_member, admin_user):
    """Sans flag, le Payment reste EN_ATTENTE (attente webhook Tara)."""
    from datetime import date
    from apps_coop.loans.models import Loan, LoanRequest
    from apps_coop.loans.services import disburse_loan_via_tara
    from apps_coop.payments.models import Payment

    lr = LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("80000"),
        duree_mois=3,
        motif="Test décaissement off",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    loan = Loan.objects.create(
        loan_request=lr,
        member=active_member,
        numero_dossier="GF-CR-TEST-002",
        montant=Decimal("80000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date(2026, 1, 1),
        date_premiere_echeance=date(2026, 2, 1),
        montant_total_du=Decimal("88000"),
        solde_restant=Decimal("88000"),
        statut=Loan.Statut.ACTIF,
    )

    payment = disburse_loan_via_tara(
        loan,
        agent=admin_user,
        recipient_phone="690000077",
        network="MTN",
    )
    assert payment.statut == Payment.Statut.EN_ATTENTE


# ---------------------------------------------------------------------------
# Frais de transaction (%) — TRANSACTION_FEE, ajouté EN PLUS du montant
# ---------------------------------------------------------------------------


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_transaction_fee_added_on_top_credits_base(
    member_client, active_member, init_payload
):
    """Frais % : Payment.frais_transaction = montant×taux, mais le compte
    n'est crédité QUE du montant de base (le membre paie montant+frais)."""
    from apps_coop.payments.models import RateParam

    RateParam.objects.update_or_create(
        code=RateParam.Code.TRANSACTION_FEE,
        defaults={"libelle": "Frais tx", "valeur": Decimal("0.02"), "actif": True},
    )
    solde_initial = active_member.savings_account.solde
    res = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    assert res.status_code == 201
    payment = Payment.objects.get(pk=res.json()["payment"]["id"])
    assert payment.frais_transaction == Decimal("20")  # 1000 × 0.02
    active_member.savings_account.refresh_from_db()
    # Crédité du MONTANT de base (1000), pas du total (1020).
    assert active_member.savings_account.solde == solde_initial + Decimal("1000")


@override_settings(PAYMENTS_TEST_AUTO_VALIDATE=True)
def test_default_transaction_fee_is_3pct_on_versement(
    member_client, active_member, init_payload
):
    """Défaut métier (sans config admin) : versement facturé 3 % en plus.

    Le taux TRANSACTION_FEE vaut 3 % par défaut et le périmètre par défaut ne
    contient que le versement : un dépôt d'épargne se voit donc appliquer 3 %,
    tandis que le compte reste crédité du seul montant de base.
    """
    solde_initial = active_member.savings_account.solde
    res = member_client.post("/api/v1/payments/init/", data=init_payload, format="json")
    assert res.status_code == 201
    payment = Payment.objects.get(pk=res.json()["payment"]["id"])
    assert payment.frais_transaction == Decimal("30")  # 1000 × 0.03
    active_member.savings_account.refresh_from_db()
    assert active_member.savings_account.solde == solde_initial + Decimal("1000")


def test_carnet_payin_gets_transaction_fee_at_init(member_client, active_member):
    """Le frais s'applique aussi au paiement de carnet (payin) : 1000 → +3%.

    Tara facture montant + frais (1030) ; le membre paie 1030 pour un carnet
    à 1000. Vérifie le périmètre « paiements entrants » configurable côté admin.
    """
    from apps_coop.payments.models import FeeType

    FeeType.objects.update_or_create(
        code=FeeType.Code.CARNET,
        defaults={"libelle": "Frais de carnet", "montant": Decimal("1000"), "actif": True},
    )
    res = member_client.post(
        "/api/v1/payments/init/",
        data={"type": "frais_carnet", "phone": "+237699112233", "network": "MTN"},
        format="json",
    )
    assert res.status_code == 201
    payment = Payment.objects.get(pk=res.json()["payment"]["id"])
    assert payment.montant == Decimal("1000")  # barème autoritaire
    assert payment.frais_transaction == Decimal("30")  # 3 % défaut, s'applique au carnet
