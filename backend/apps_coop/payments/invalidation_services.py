"""Invalidation d'un paiement VALIDÉ par l'administration (contre-passation).

L'admin peut TOUJOURS invalider un paiement : on passe le ``Payment`` en
``REJETE`` et on **contre-passe son effet ledger** :

  * écritures de collecte journalière (``SavingsTransaction``) ;
  * écritures d'épargne classique / placement (``ClassicSavingsTransaction``) ;
  * imputations de remboursement crédit (``LoanRepayment``) — le solde du crédit
    est restauré et l'échéance ré-ouverte.

Chaque contre-passation crée une écriture de sens inverse (traçabilité) reliée
au même paiement. Le décaissement (``DECAISSEMENT``) n'est PAS invalidable ici
(opération lourde à traiter séparément).
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import Payment


logger = logging.getLogger(__name__)


class PaymentInvalidationError(ValueError):
    """Invalidation impossible (motif lisible par l'admin)."""


def _reverse_collecte_tx(tx) -> None:
    from apps_coop.savings.models import SavingsTransaction

    T = SavingsTransaction.TypeOp
    credit = {T.DEPOT, T.INTERET}
    # Tout le reste (RETRAIT, RETRAIT_FORCE, COMMISSION, RESTITUTION_CASH,
    # BASCULE_EPARGNE) est un débit de la collecte.
    account = tx.account
    montant = tx.montant
    if tx.type_op in credit:
        account.solde = account.solde - montant  # annule un crédit
        reverse_op = T.RETRAIT
    else:
        account.solde = account.solde + montant  # annule un débit
        reverse_op = T.DEPOT
    account.save(update_fields=["solde", "updated_at"])
    SavingsTransaction.objects.create(
        account=account,
        payment=tx.payment,
        type_op=reverse_op,
        montant=montant,
        solde_apres=account.solde,
        date=timezone.now(),
    )


def _reverse_classic_tx(tx) -> None:
    from apps_coop.savings.models import ClassicSavingsTransaction

    T = ClassicSavingsTransaction.TypeOp
    credit = {T.DEPOT, T.INTERET, T.INTERET_PLACEMENT, T.INTERET_PRETEUR, T.BASCULE_COLLECTE}
    info_only = {T.RESTITUTION_PLACEMENT}  # ligne informative : solde inchangé
    if tx.type_op in info_only:
        return
    account = tx.account
    montant = tx.montant
    if tx.type_op in credit:
        account.solde = account.solde - montant
        reverse_op = T.RETRAIT
    else:
        account.solde = account.solde + montant
        reverse_op = T.DEPOT
    account.save(update_fields=["solde", "updated_at"])
    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=tx.payment,
        type_op=reverse_op,
        montant=montant,
        solde_apres=account.solde,
        date=timezone.now(),
    )


def _reverse_repayment(rep) -> None:
    from apps_coop.loans.models import Loan, LoanInstallment

    inst = rep.installment
    loan = inst.loan
    montant = rep.montant_impute

    # Restaure l'échéance. (``interets_payes`` — suivi du partage prêteur — est
    # laissé tel quel : la contre-passation d'un éventuel reversement prêteur est
    # hors périmètre de cette invalidation.)
    inst.montant_paye = max(inst.montant_paye - montant, 0)
    if inst.montant_paye <= 0:
        inst.montant_paye = 0
        past_due = inst.date_echeance < timezone.localdate()
        inst.statut = (
            LoanInstallment.Statut.EN_RETARD
            if past_due
            else LoanInstallment.Statut.A_VENIR
        )
    elif inst.montant_paye < inst.montant_total:
        inst.statut = LoanInstallment.Statut.PARTIELLE
    else:
        inst.statut = LoanInstallment.Statut.PAYEE
    inst.save(update_fields=["montant_paye", "statut", "updated_at"])

    # Restaure le solde du crédit et ré-ouvre s'il était clôturé.
    loan.solde_restant = loan.solde_restant + montant
    if loan.statut == Loan.Statut.CLOTURE:
        loan.statut = Loan.Statut.ACTIF
    loan.save(update_fields=["solde_restant", "statut", "updated_at"])

    rep.delete()


@transaction.atomic
def invalidate_payment(payment: Payment, *, actor, motif: str = "") -> Payment:
    """Invalide un paiement VALIDÉ et contre-passe son effet. Idempotent (refuse
    un paiement déjà REJETE). Lève ``PaymentInvalidationError`` sinon."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)

    if payment.statut == Payment.Statut.REJETE:
        raise PaymentInvalidationError("Ce paiement est déjà invalidé.")
    if payment.statut != Payment.Statut.VALIDE:
        raise PaymentInvalidationError(
            f"Seul un paiement VALIDÉ peut être invalidé (statut : {payment.statut})."
        )
    if payment.type == Payment.Type.DECAISSEMENT:
        raise PaymentInvalidationError(
            "Un décaissement ne s'invalide pas ici — traitez le crédit "
            "directement (remboursement / clôture)."
        )

    reversed_summary = {
        "collecte_tx": payment.savings_transactions.count(),
        "classic_tx": payment.classic_savings_transactions.count(),
        "repayments": payment.loan_repayments.count(),
    }

    for tx in payment.savings_transactions.select_related("account").all():
        _reverse_collecte_tx(tx)
    for tx in payment.classic_savings_transactions.select_related("account").all():
        _reverse_classic_tx(tx)
    for rep in payment.loan_repayments.select_related(
        "installment", "installment__loan"
    ).all():
        _reverse_repayment(rep)

    payment.statut = Payment.Statut.REJETE
    payment.save(update_fields=["statut", "updated_at"])

    record_audit(
        action="payment.invalidated",
        entite_type="Payment",
        entite_id=payment.id,
        user=actor,
        details={
            "type": payment.type,
            "source": payment.source,
            "montant": str(payment.montant),
            "motif": (motif or "").strip(),
            "reversed": reversed_summary,
        },
    )
    return payment
