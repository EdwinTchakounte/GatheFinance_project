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
from decimal import Decimal

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
        # Borne à 0 : si le membre a déjà retiré les fonds, on n'écrit pas un
        # solde négatif (l'écart éventuel reste tracé par l'écriture inverse).
        account.solde = max(account.solde - montant, Decimal("0"))  # annule un crédit
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
    from apps_coop.savings.models import ClassicSavingsTransaction, LenderTranche

    T = ClassicSavingsTransaction.TypeOp
    credit = {T.DEPOT, T.INTERET, T.INTERET_PLACEMENT, T.INTERET_PRETEUR, T.BASCULE_COLLECTE}
    info_only = {T.RESTITUTION_PLACEMENT}  # ligne informative : solde inchangé
    if tx.type_op in info_only:
        return

    # Contre-passation de la tranche prêteur créée par un dépôt PLACEMENT : sinon
    # une tranche DISPONIBLE restait orpheline (argent fantôme mobilisable). Si la
    # tranche est déjà ENGAGEE/GELEE (elle finance ou garantit un crédit), on
    # REFUSE l'invalidation — traiter le crédit d'abord.
    if tx.type_op == T.DEPOT and tx.is_placement:
        for tr in tx.lender_tranches.all():
            if tr.statut == LenderTranche.Statut.DISPONIBLE:
                tr.statut = LenderTranche.Statut.ANNULEE
                tr.save(update_fields=["statut", "updated_at"])
            elif tr.statut in {
                LenderTranche.Statut.ENGAGEE,
                LenderTranche.Statut.GELEE,
            }:
                raise PaymentInvalidationError(
                    "Ce dépôt placement finance ou garantit déjà un crédit "
                    "(tranche engagée/gelée) — invalidation impossible. Traitez "
                    "d'abord le crédit concerné."
                )
            # LIBEREE / ANNULEE : rien à faire.

    account = tx.account
    montant = tx.montant
    if tx.type_op in credit:
        account.solde = max(account.solde - montant, Decimal("0"))
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
    # Les frais déclenchent des effets en cascade non contre-passables de façon
    # générique et sûre : activation du membre (adhésion/inscription/carnet),
    # commande de carnet, avancement d'une demande de crédit (frais d'étude),
    # cycle de reconduction. Les invalider en aveugle laisserait le système
    # incohérent (membre ACTIF alors que le frais est REJETE, demande « frais
    # payés », carnet fantôme). On refuse ici — le cas se traite via la fiche
    # membre / la demande de crédit concernée.
    _FEE_TYPES = {
        Payment.Type.FRAIS_ADHESION,
        Payment.Type.FRAIS_INSCRIPTION,
        Payment.Type.FRAIS_CARNET,
        Payment.Type.FRAIS_DEMANDE_CREDIT,
        Payment.Type.FRAIS_RECONDUCTION,
    }
    if payment.type in _FEE_TYPES:
        raise PaymentInvalidationError(
            "Un paiement de frais (adhésion, inscription, carnet, demande de "
            "crédit, reconduction) ne peut pas être invalidé ici : il déclenche "
            "l'activation du membre, la commande de carnet ou l'avancement d'une "
            "demande. Traitez le cas via la fiche membre ou la demande concernée."
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
