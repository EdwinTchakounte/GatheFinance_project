"""Débit manuel direct (agence) sur un compte membre — 2026-08.

Symétrique du cash-in agence, mais en NÉGATIF. Deux modes :

  1. **Retrait simple** (``fee_code=None``) : débite immédiatement le compte
     choisi du montant saisi, avec un libellé. Refuse si le disponible est
     insuffisant. Comptes possibles : collecte journalière, épargne classique,
     et — depuis 2026-09 — les collectes particulières (``tontine`` /
     ``caisse``), dont le décaissement était jusqu'ici réservé à l'écran
     « collectes » alors qu'il s'agit du même geste de caisse.

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
    # Carnets dédiés aux collectes particulières : un carnet par type, donc un
    # frais par type. Ils manquaient ici alors que le carnet est OBLIGATOIRE
    # pour verser dans une tontine/caisse — l'admin ne pouvait pas régler ce
    # frais depuis l'épargne, contrairement à tous les autres.
    FeeType.Code.CARNET_TONTINE: Payment.Type.FRAIS_CARNET_TONTINE,
    FeeType.Code.CARNET_CAISSE: Payment.Type.FRAIS_CARNET_CAISSE,
    FeeType.Code.RECONDUCTION: Payment.Type.FRAIS_RECONDUCTION,
}

#: ``compte`` accepté → type de collecte particulière correspondant.
_SPECIAL_COMPTE_TO_TYPE = {
    "tontine": "tontine_alimentaire",
    "caisse": "caisse_scolaire",
}


def manual_debit(
    *, member, compte="classique", montant=None, motif="", fee_code=None,
    is_renewal=False, cycle_id=None, destination="cash", actor=None,
):
    """``cycle_id`` / ``destination`` ne concernent que les comptes de collecte
    particulière (``tontine`` / ``caisse``) : ils désignent la collecte visée et
    la sortie de l'argent (espèces à l'agence, ou bascule vers l'épargne
    classique du membre)."""
    if fee_code:
        return _debit_fee(
            member=member, fee_code=fee_code, montant=montant,
            is_renewal=is_renewal, actor=actor,
        )
    if compte in _SPECIAL_COMPTE_TO_TYPE:
        return _debit_special_collection(
            member=member, compte=compte, montant=montant, motif=motif,
            cycle_id=cycle_id, destination=destination, actor=actor,
        )
    return _debit_simple(
        member=member, compte=compte, montant=montant, motif=motif, actor=actor,
    )


# ── Retrait sur une collecte particulière (tontine / caisse scolaire) ────────
def _debit_special_collection(
    *, member, compte, montant, motif, cycle_id, destination, actor,
):
    """Décaisse le solde d'un participant à une collecte particulière.

    On **délègue** à ``decaisser_participation`` plutôt que de re-débiter le
    solde ici : c'est le service qui porte déjà les règles (refus au-delà du
    solde, écriture RETRAIT rattachée au carnet du type, crédit de l'épargne si
    ``destination="epargne"``, audit). Dupliquer l'aurait fait diverger au
    premier changement de règle — pour de l'argent réel, c'est inacceptable.

    ``cycle_id`` est facultatif tant que la situation est NON AMBIGUË : s'il
    existe plusieurs participations approvisionnées pour ce type, on refuse et
    on demande laquelle — deviner reviendrait à débiter la mauvaise collecte.
    """
    from apps_coop.special_collections.models import SpecialCollectionMembership
    from apps_coop.special_collections.services import (
        SpecialCollectionError,
        decaisser_participation,
    )

    collection_type = _SPECIAL_COMPTE_TO_TYPE[compte]

    if cycle_id is None:
        # On filtre sur ``cycle__type`` et non sur ``membership.type`` : le
        # cycle porte toujours son type (il est requis à sa création), alors
        # que la colonne dénormalisée de la participation peut être vide sur
        # des lignes anciennes — s'y fier ferait rater des soldes bien réels.
        candidates = list(
            SpecialCollectionMembership.objects.filter(
                member=member, cycle__type=collection_type, solde__gt=0,
            ).select_related("cycle").order_by("-cycle__date_debut", "-id")
        )
        if not candidates:
            raise ManualDebitError(
                "Aucune participation approvisionnée pour ce membre dans cette "
                "collecte."
            )
        if len(candidates) > 1:
            libelles = ", ".join(
                f"#{m.cycle_id} {m.cycle.nom} ({int(Decimal(m.solde))} XAF)"
                for m in candidates
            )
            raise ManualDebitError(
                "Ce membre a plusieurs collectes approvisionnées de ce type — "
                f"précise laquelle débiter : {libelles}."
            )
        cycle_id = candidates[0].cycle_id

    try:
        row = decaisser_participation(
            member=member,
            cycle_id=cycle_id,
            montant=Decimal(str(montant or "0")),
            destination=destination,
            note=motif,
            by=actor,
        )
    except SpecialCollectionError as exc:
        # Traduit vers l'erreur du module pour que l'endpoint réponde 400,
        # comme pour les autres comptes.
        raise ManualDebitError(str(exc)) from exc

    record_audit(
        action="savings.manual_debit",
        entite_type="SpecialCollectionTransaction",
        entite_id=row.id,
        user=actor,
        details={
            "member_id": member.id, "compte": compte,
            "cycle_id": cycle_id, "destination": destination,
            "montant": str(row.montant), "motif": (motif or "").strip()[:200],
            "solde_apres": str(row.solde_apres),
        },
    )
    return {
        "transaction_id": row.id, "compte": compte, "cycle_id": cycle_id,
        "destination": destination, "montant": str(row.montant),
        "solde_apres": str(row.solde_apres),
    }


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
            raise ManualDebitError(
                "Compte inconnu (collecte / classique / tontine / caisse)."
            )

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
