"""Paiement des frais de membre (adhésion / inscription) depuis l'épargne.

G7 / G5 (refonte 2026-07) : depuis le carrousel de la home (paiement adhésion /
inscription) ou pour se **réactiver** après une clôture de cycle, le membre peut
régler ses frais soit en Mobile Money (``/payments/init/``), soit **depuis son
compte s'il est solvable** — transfert interne : le ``Payment`` naît VALIDE et
déclenche le hook d'activation/réactivation (``_hook_adhesion``).

Ponction : épargne classique retirable d'abord, puis collecte. Le placement et
l'épargne gelée en garantie ne sont jamais ponctionnés.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit


class FeePaymentError(ValueError):
    """Le règlement du frais est impossible (motif lisible par le membre)."""


# Codes des 3 frais d'activation → Payment.Type correspondant (chacun peut être
# réglé depuis l'épargne ; le carnet passe par son propre hook).
_FEE_CODE_TO_PAYMENT_TYPE = {
    "ADHESION": "frais_adhesion",
    "INSCRIPTION": "frais_inscription",
    "CARNET": "frais_carnet",
}


def membership_fee_amount(fee_code: str) -> Decimal:
    from apps_coop.payments.models import FeeType

    ft = FeeType.objects.filter(code=fee_code, actif=True).first()
    return Decimal(ft.montant) if ft else Decimal("0")


def available_for_fees(member) -> Decimal:
    """Argent mobilisable : épargne classique retirable + collecte."""
    from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
    from apps_coop.savings.services import classic_withdrawable

    classic = ClassicSavingsAccount.objects.filter(member=member).first()
    collecte = SavingsAccount.objects.filter(member=member).first()
    dispo = classic_withdrawable(classic) if classic else Decimal("0")
    dispo += Decimal(collecte.solde) if collecte else Decimal("0")
    return dispo


@transaction.atomic
def pay_membership_fee_from_savings(member, fee_code: str) -> "object":
    """Règle un frais membre (ADHESION | INSCRIPTION) en puisant dans l'épargne.

    Renvoie le ``Payment`` (VALIDE). Lève ``FeePaymentError`` si le code est
    inconnu, le montant nul, ou l'épargne disponible insuffisante.
    """
    from apps_coop.payments.models import Payment
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )
    from apps_coop.savings.services import classic_withdrawable

    payment_type = _FEE_CODE_TO_PAYMENT_TYPE.get(fee_code)
    if payment_type is None:
        raise FeePaymentError(
            "Type de frais non réglable depuis le compte "
            "(seuls adhésion, inscription et carnet le sont)."
        )

    montant = membership_fee_amount(fee_code)
    if montant <= 0:
        raise FeePaymentError("Montant du frais introuvable ou nul.")

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
    if classic_dispo + collecte_solde < montant:
        raise FeePaymentError(
            f"Épargne disponible insuffisante : {classic_dispo + collecte_solde} "
            f"XAF pour {montant} XAF de frais. Règle en Mobile Money."
        )

    now = timezone.now()
    payment = Payment.objects.create(
        member=member,
        montant=montant,
        type=payment_type,
        source=Payment.Source.DEDUCTION_EPARGNE,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )

    reste = montant
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

    record_audit(
        action="member.fee_paid_from_savings",
        entite_type="Member",
        entite_id=member.id,
        details={"payment_id": payment.id, "fee_code": fee_code, "montant": str(montant)},
    )

    # Payment VALIDE → hook métier selon le frais. Le carnet crée en plus la
    # commande de carnet (BookletOrder) ; adhésion/inscription passent par
    # _hook_adhesion. Les deux tentent l'activation si les 3 frais sont soldés.
    from apps_coop.payments.services import _hook_adhesion, _hook_carnet_fees

    if fee_code == "CARNET":
        _hook_carnet_fees(payment, {})
    else:
        _hook_adhesion(payment, {})
    return payment
