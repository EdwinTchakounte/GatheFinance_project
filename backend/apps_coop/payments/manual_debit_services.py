"""Débit manuel direct (agence) sur un compte membre — 2026-08.

Symétrique du cash-in agence, mais en NÉGATIF. Deux modes :

  1. **Retrait simple** (``fee_code=None``) : débite immédiatement le compte
     choisi (collecte journalière OU épargne classique) du montant saisi, avec
     un libellé. Refuse si le disponible est insuffisant.

  2. **Prélèvement d'un frais** (``fee_code`` fourni) : règle un frais du barème
     (réinscription/carnet…) en le prélevant sur l'épargne classique — crée un
     ``Payment`` (source ``DEDUCTION_EPARGNE``, VALIDE) et exécute le hook métier
     du frais (activation / renouvellement / carnet). Un seul geste.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder

from .models import FeeType, Payment


class ManualDebitError(ValueError):
    """Débit manuel impossible (compte, solde, frais…)."""


# Frais du barème réglables par prélèvement épargne + type de Payment associé.
_FEE_CODE_TO_TYPE = {
    FeeType.Code.INSCRIPTION: Payment.Type.FRAIS_INSCRIPTION,
    FeeType.Code.ADHESION: Payment.Type.FRAIS_ADHESION,
    FeeType.Code.CARNET: Payment.Type.FRAIS_CARNET,
    FeeType.Code.RECONDUCTION: Payment.Type.FRAIS_RECONDUCTION,
}


def manual_debit(
    *, member, compte="classique", montant=None, motif="", fee_code=None,
    is_renewal=False, actor=None,
):
    if fee_code:
        return _debit_fee(
            member=member, fee_code=fee_code, montant=montant,
            is_renewal=is_renewal, actor=actor,
        )
    return _debit_simple(
        member=member, compte=compte, montant=montant, motif=motif, actor=actor,
    )


# ── Retrait simple (collecte ou classique) ──────────────────────────────────
def _debit_simple(*, member, compte, montant, motif, actor):
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )
    from apps_coop.savings.services import (
        classic_withdrawable,
        reserved_withdrawals,
    )

    montant = Decimal(str(montant or "0"))
    if montant <= 0:
        raise ManualDebitError("Le montant doit être strictement positif.")

    now = timezone.now()
    with db_transaction.atomic():
        if compte == "collecte":
            account = (
                SavingsAccount.objects.select_for_update()
                .filter(member=member)
                .first()
            )
            if account is None:
                raise ManualDebitError("Aucun compte de collecte pour ce membre.")
            dispo = Decimal(account.solde) - reserved_withdrawals(account=account)
            if montant > dispo:
                raise ManualDebitError(
                    f"Disponible insuffisant : {int(dispo)} XAF retirables."
                )
            account.solde = Decimal(account.solde) - montant
            account.save(update_fields=["solde", "updated_at"])
            row = SavingsTransaction.objects.create(
                account=account,
                type_op=SavingsTransaction.TypeOp.RETRAIT,
                montant=montant,
                solde_apres=account.solde,
                date=now,
                booklet_order=BookletOrder.latest_for(member),
            )
            entite = "SavingsTransaction"
            solde_apres = account.solde
        elif compte == "classique":
            account = (
                ClassicSavingsAccount.objects.select_for_update()
                .filter(member=member)
                .first()
            )
            if account is None:
                raise ManualDebitError("Aucun compte d'épargne classique.")
            dispo = classic_withdrawable(account)
            if montant > dispo:
                raise ManualDebitError(
                    f"Disponible insuffisant : {int(dispo)} XAF retirables "
                    f"(placement/gel exclus)."
                )
            account.solde = Decimal(account.solde) - montant
            account.save(update_fields=["solde", "updated_at"])
            row = ClassicSavingsTransaction.objects.create(
                account=account,
                type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
                montant=montant,
                solde_apres=account.solde,
                date=now,
                booklet_order=BookletOrder.latest_for(member),
            )
            entite = "ClassicSavingsTransaction"
            solde_apres = account.solde
        else:
            raise ManualDebitError("Compte inconnu (collecte / classique).")

    record_audit(
        action="savings.manual_debit",
        entite_type=entite,
        entite_id=row.id,
        user=actor,
        details={
            "member_id": member.id, "compte": compte,
            "montant": str(montant), "motif": (motif or "").strip()[:200],
            "solde_apres": str(solde_apres),
        },
    )
    return {"transaction_id": row.id, "compte": compte,
            "montant": str(montant), "solde_apres": str(solde_apres)}


# ── Prélèvement d'un frais depuis l'épargne classique ───────────────────────
def _debit_fee(*, member, fee_code, montant, is_renewal, actor):
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )
    from apps_coop.savings.services import classic_withdrawable

    payment_type = _FEE_CODE_TO_TYPE.get(fee_code)
    if payment_type is None:
        raise ManualDebitError("Ce frais ne peut pas être prélevé ici.")

    # Montant autoritaire : le tarif officiel du barème prime.
    official = (
        FeeType.objects.filter(code=fee_code, actif=True)
        .values_list("montant", flat=True)
        .first()
    )
    if official is None or official <= 0:
        raise ManualDebitError("Aucun tarif configuré pour ce frais.")
    montant = Decimal(official)

    now = timezone.now()
    with db_transaction.atomic():
        account = (
            ClassicSavingsAccount.objects.select_for_update()
            .filter(member=member)
            .first()
        )
        if account is None:
            raise ManualDebitError("Aucun compte d'épargne classique.")
        dispo = classic_withdrawable(account)
        if montant > dispo:
            raise ManualDebitError(
                f"Disponible insuffisant : {int(dispo)} XAF retirables pour "
                f"{int(montant)} XAF de frais."
            )
        account.solde = Decimal(account.solde) - montant
        account.save(update_fields=["solde", "updated_at"])

        payment = Payment.objects.create(
            member=member,
            montant=montant,
            type=payment_type,
            source=Payment.Source.DEDUCTION_EPARGNE,
            statut=Payment.Statut.VALIDE,
            validated_by=actor,
            date_versement=now,
            date_validation=now,
        )
        ClassicSavingsTransaction.objects.create(
            account=account,
            payment=payment,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=montant,
            solde_apres=account.solde,
            date=now,
            booklet_order=BookletOrder.latest_for(member),
        )
        # Exécute le hook métier du frais (activation / renouvellement / carnet).
        from .services import _BUSINESS_HOOKS

        hook = _BUSINESS_HOOKS.get(payment.type)
        if hook is not None:
            hook(payment, {"is_renewal": bool(is_renewal)})

    record_audit(
        action="payment.fee_paid_from_savings_manual",
        entite_type="Payment",
        entite_id=payment.id,
        user=actor,
        details={"member_id": member.id, "fee_code": fee_code,
                 "montant": str(montant), "is_renewal": bool(is_renewal)},
    )
    return {"payment_id": payment.id, "fee_code": fee_code,
            "montant": str(montant), "solde_apres": str(account.solde)}
