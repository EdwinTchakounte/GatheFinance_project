"""Transfert interne — rembourser un crédit depuis l'épargne du membre.

G6 (refonte 2026-07) : depuis la home, l'action « Transfert » permet de
rembourser un crédit en cours en puisant dans l'argent **disponible** du
membre : épargne classique **non gelée** (part retirable) + collecte
journalière. Aucun encaissement Mobile Money — c'est un transfert interne, le
``Payment`` naît VALIDE et déclenche directement le hook de remboursement.

Ordre de ponction : épargne classique retirable d'abord, puis collecte.
Le placement et l'épargne gelée en garantie ne sont **jamais** ponctionnés
(``classic_withdrawable`` les exclut déjà).
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import Loan


# Versement minimum (règle 2026 « 1 000 partout »). EXCEPTION : un versement qui
# solde le reste dû est toujours accepté, même s'il est < 1 000 — sinon on
# bloquerait la clôture d'un petit reliquat. Partagé avec le chemin Mobile Money
# (apps_coop.payments.views).
MIN_REPAYMENT_XAF = Decimal("1000")


class TransferError(ValueError):
    """Le transfert est impossible (motif lisible par le membre)."""


def available_for_transfer(member) -> dict:
    """Argent mobilisable pour un remboursement : classique retirable + collecte."""
    from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
    from apps_coop.savings.services import classic_withdrawable

    classic = ClassicSavingsAccount.objects.filter(member=member).first()
    collecte = SavingsAccount.objects.filter(member=member).first()
    classic_dispo = classic_withdrawable(classic) if classic else Decimal("0")
    collecte_solde = Decimal(collecte.solde) if collecte else Decimal("0")
    return {
        "classic": classic_dispo,
        "collecte": collecte_solde,
        "total": classic_dispo + collecte_solde,
    }


@transaction.atomic
def repay_loan_from_savings(loan: Loan, montant: Decimal) -> "object":
    """Rembourse ``montant`` sur ``loan`` en puisant dans l'épargne disponible.

    Renvoie le ``Payment`` (VALIDE) créé. Lève ``TransferError`` si le crédit
    n'est pas remboursable, si le montant est invalide ou si l'argent
    disponible est insuffisant.
    """
    from apps_coop.payments.models import Payment
    from apps_coop.payments.services import _hook_loan_repayment
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )
    from apps_coop.savings.services import classic_withdrawable

    montant = Decimal(montant)
    if montant <= 0:
        raise TransferError("Le montant doit être supérieur à 0.")

    if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
        raise TransferError("Ce crédit n'est pas remboursable (déjà clôturé ?).")

    solde_restant = Decimal(loan.solde_restant)
    if solde_restant <= 0:
        raise TransferError("Ce crédit est déjà soldé.")
    # On ne rembourse jamais plus que ce qui reste dû.
    if montant > solde_restant:
        montant = solde_restant

    # Plancher 1 000 XAF, SAUF si ce versement solde le reste dû (petit reliquat).
    if montant < MIN_REPAYMENT_XAF and montant < solde_restant:
        raise TransferError(
            f"Le versement minimum est de {int(MIN_REPAYMENT_XAF)} XAF "
            "(sauf pour solder le reste dû)."
        )

    member = loan.member

    classic = (
        ClassicSavingsAccount.objects.select_for_update()
        .filter(member=member)
        .first()
    )
    collecte = (
        SavingsAccount.objects.select_for_update().filter(member=member).first()
    )
    classic_dispo = classic_withdrawable(classic) if classic else Decimal("0")
    collecte_solde = Decimal(collecte.solde) if collecte else Decimal("0")
    total_dispo = classic_dispo + collecte_solde

    if total_dispo < montant:
        raise TransferError(
            f"Argent disponible insuffisant : {total_dispo} XAF mobilisables "
            f"(épargne retirable + collecte) pour {montant} XAF. Le placement "
            f"et l'épargne gelée en garantie ne sont pas ponctionnables."
        )

    now = timezone.now()

    payment = Payment.objects.create(
        member=member,
        loan=loan,
        montant=montant,
        type=Payment.Type.REMBOURSEMENT,
        source=Payment.Source.DEDUCTION_EPARGNE,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )

    reste = montant
    pris_classique = Decimal("0")
    pris_collecte = Decimal("0")

    # 1) Épargne classique retirable d'abord.
    if classic is not None and classic_dispo > 0 and reste > 0:
        pris = min(classic_dispo, reste)
        classic.solde = Decimal(classic.solde) - pris
        classic.save(update_fields=["solde", "updated_at"])
        ClassicSavingsTransaction.objects.create(
            account=classic,
            payment=payment,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=pris,
            solde_apres=classic.solde,
            date=now,
        )
        reste -= pris
        pris_classique = pris

    # 2) Puis la collecte journalière.
    if collecte is not None and reste > 0:
        pris = min(collecte_solde, reste)
        collecte.solde = Decimal(collecte.solde) - pris
        collecte.save(update_fields=["solde", "updated_at"])
        SavingsTransaction.objects.create(
            account=collecte,
            payment=payment,
            type_op=SavingsTransaction.TypeOp.RETRAIT,
            montant=pris,
            solde_apres=collecte.solde,
            date=now,
        )
        reste -= pris
        pris_collecte = pris

    record_audit(
        action="loan.repayment_from_savings",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "payment_id": payment.id,
            "montant": str(montant),
            "pris_classique": str(pris_classique),
            "pris_collecte": str(pris_collecte),
        },
    )

    # Le Payment naît VALIDE → on impute nous-mêmes sur les échéances.
    _hook_loan_repayment(payment, {})
    return payment
