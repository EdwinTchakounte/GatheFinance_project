"""Partage 50/50 des intérêts crédit (refonte 2026 §7.5 / LOT 9).

Exporté pour ``apps_coop.payments.services._hook_loan_repayment`` qui pose les
``LoanRepayment`` puis appelle ``distribute_interest_share`` pour chaque
imputation. Aussi exporté pour le helper de clôture ``release_loan_tranches``,
appelé quand toutes les échéances passent à PAYEE.

Contrat de l'API (idempotence + sûreté) :
  * ``distribute_interest_share`` n'agit que sur les imputations dont la
    portion intérêt > 0. La portion intérêt est calculée en priorité avant
    le capital, et bornée par les intérêts restants dus.
  * Le crédit du compte épargne classique du prêteur est *append-only* :
    ``ClassicSavingsTransaction(INTERET_PRETEUR)`` + ``solde_apres`` figé.
  * ``release_loan_tranches`` ne libère que les tranches ENGAGEE — toute
    réexécution est un no-op (idempotent).

Le découpage ``intérêt_pretteurs / intérêt_coop`` est tunable via
``lender.interest_share_rate`` (défaut 0.5). 0 désactive complètement le
partage (utilisé pour les crédits antérieurs au LOT 7 sans LenderAllocation).
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps_coop.audit.services import get_str_setting, record as record_audit
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    LenderTranche,
)

from .models import (
    LenderAllocation,
    LenderInterestPayout,
    Loan,
    LoanInstallment,
)


logger = logging.getLogger(__name__)


def _q(x: Decimal) -> Decimal:
    """Arrondi 2 décimales (XAF n'a pas de fraction mais on garde la précision)."""
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _share_rate() -> Decimal:
    """Lit ``lender.interest_share_rate`` (str AppSetting) en Decimal sûr."""
    raw = get_str_setting("lender.interest_share_rate", "0.5")
    try:
        rate = Decimal(str(raw).strip())
    except Exception:  # noqa: BLE001 — admin a mis n'importe quoi
        logger.warning(
            "lender.interest_share_rate invalide (%r), fallback 0.5", raw
        )
        rate = Decimal("0.5")
    if rate < 0 or rate > 1:
        logger.warning(
            "lender.interest_share_rate hors [0,1] (%s), clamp", rate
        )
        rate = max(Decimal("0"), min(Decimal("1"), rate))
    return rate


def _allocations_for_loan(loan: Loan) -> list[LenderAllocation]:
    """Liste verrouillée des allocations prêteurs du crédit (vide si crédit legacy)."""
    return list(
        LenderAllocation.objects.select_for_update()
        .filter(loan=loan)
        .select_related("lender")
        .order_by("id")
    )


def compute_interest_portion(
    installment: LoanInstallment, imputation: Decimal
) -> Decimal:
    """Portion *intérêt* d'une imputation, dans la limite des intérêts restants.

    Politique : on paie l'intérêt avant le capital. Si l'échéance a déjà été
    soldée côté intérêts (``interets_payes >= montant_interets``), la portion
    est 0 et le repayment alimente uniquement le capital.

    L'appelant garantit que ``imputation > 0`` et que l'échéance n'est pas
    purement pénalité (cas atypique géré côté hook : pénalité imputée à part).
    """
    interets_dus = Decimal(installment.montant_interets)
    deja_paye = Decimal(installment.interets_payes)
    restant = max(Decimal("0"), interets_dus - deja_paye)
    if restant <= 0 or imputation <= 0:
        return Decimal("0")
    return min(Decimal(imputation), restant)


@transaction.atomic
def distribute_interest_share(
    *,
    installment: LoanInstallment,
    payment,
    imputation: Decimal,
) -> list[LenderInterestPayout]:
    """Calcule + reverse la part prêteurs d'une imputation. Retourne les payouts.

    No-op (retourne ``[]``) si :
      • le crédit n'a aucune ``LenderAllocation`` (crédit legacy pré-LOT 7),
      • la portion intérêt de l'imputation est nulle,
      • ``lender.interest_share_rate == 0`` (kill-switch).

    En cas d'arrondi (la somme des shares ne tombe pas pile sur la part
    pretteurs cible), l'écart résiduel est attribué à la **dernière**
    allocation pour que ``somme(payouts) == intérêt_pretteurs``.
    """
    loan = installment.loan
    allocations = _allocations_for_loan(loan)
    if not allocations:
        # Crédit financé directement par la coop avant la refonte 2026,
        # ou jamais passé par funding_services — pas de partage.
        return []

    interet_imputation = compute_interest_portion(installment, imputation)
    if interet_imputation <= 0:
        return []

    share_rate = _share_rate()
    if share_rate <= 0:
        return []

    pretteurs_total = _q(interet_imputation * share_rate)
    if pretteurs_total <= 0:
        return []

    payouts: list[LenderInterestPayout] = []
    now = timezone.now()
    sum_dispatched = Decimal("0")
    for idx, alloc in enumerate(allocations):
        share = _q(pretteurs_total * Decimal(alloc.quote_part))
        # Dernière allocation absorbe le résidu d'arrondi.
        if idx == len(allocations) - 1:
            share = _q(pretteurs_total - sum_dispatched)
        if share <= 0:
            continue
        payout = _credit_lender(
            allocation=alloc,
            installment=installment,
            payment=payment,
            montant=share,
            when=now,
        )
        payouts.append(payout)
        sum_dispatched += share

    # Mise à jour du tracker installment + cumul allocation.
    installment.interets_payes = _q(
        Decimal(installment.interets_payes) + interet_imputation
    )
    installment.save(update_fields=["interets_payes", "updated_at"])

    record_audit(
        action="loan.interest_share_distributed",
        entite_type="LoanInstallment",
        entite_id=installment.id,
        details={
            "loan_id": loan.id,
            "payment_id": payment.id,
            "imputation": str(imputation),
            "interet_imputation": str(interet_imputation),
            "share_rate": str(share_rate),
            "pretteurs_total": str(pretteurs_total),
            "payouts": [
                {
                    "allocation_id": p.allocation_id,
                    "lender_id": p.allocation.lender_id,
                    "montant": str(p.montant),
                }
                for p in payouts
            ],
        },
    )
    return payouts


def _credit_lender(
    *,
    allocation: LenderAllocation,
    installment: LoanInstallment,
    payment,
    montant: Decimal,
    when,
) -> LenderInterestPayout:
    """Crédite le solde du prêteur + pose payout + cumul allocation.

    Crée le ``ClassicSavingsAccount`` à la volée si le prêteur n'en a pas
    encore (cas rare : il aurait signé la convention sans avoir versé sur
    le compte classique — la convention n'impose pas l'existence du compte).
    """
    lender = allocation.lender
    account, _ = ClassicSavingsAccount.objects.select_for_update().get_or_create(
        member=lender,
        defaults={
            "solde": Decimal("0"),
            "date_ouverture": when.date(),
        },
    )
    nouveau_solde = Decimal(account.solde) + montant
    account.solde = nouveau_solde
    account.save(update_fields=["solde", "updated_at"])

    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.INTERET_PRETEUR,
        montant=montant,
        solde_apres=nouveau_solde,
        date=when,
    )

    payout = LenderInterestPayout.objects.create(
        allocation=allocation,
        installment=installment,
        payment=payment,
        montant=montant,
        date=when,
    )
    allocation.interest_share_paid_total = _q(
        Decimal(allocation.interest_share_paid_total) + montant
    )
    allocation.save(update_fields=["interest_share_paid_total", "updated_at"])

    # Event best-effort — un projet sans notifications.events configuré ne
    # doit pas casser un remboursement.
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            "lender.interest_paid",
            member=lender,
            context={
                "prenom": lender.prenom,
                "montant": str(montant),
                "numero_dossier": allocation.loan.numero_dossier,
                "echeance": installment.numero_echeance,
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning(
            "emit_event lender.interest_paid a échoué (payout=%s)", payout.id
        )
    return payout


@transaction.atomic
def release_loan_tranches(loan: Loan) -> int:
    """Libère toutes les tranches ENGAGEE du crédit. Retourne le nb libéré.

    Idempotent : un second appel sur un crédit dont les tranches sont déjà
    LIBEREE retourne 0 et ne touche pas la base. Appelé par
    ``payments.services._hook_loan_repayment`` au passage du crédit en
    ``CLOTURE``.
    """
    now = timezone.now()
    engaged = list(
        LenderTranche.objects.select_for_update()
        .filter(engaged_in_loan=loan, statut=LenderTranche.Statut.ENGAGEE)
    )
    if not engaged:
        return 0

    for tranche in engaged:
        tranche.statut = LenderTranche.Statut.LIBEREE
        tranche.released_at = now
        tranche.save(update_fields=["statut", "released_at", "updated_at"])

    record_audit(
        action="loan.tranches_released",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "tranche_ids": [t.id for t in engaged],
            "count": len(engaged),
        },
    )
    return len(engaged)


# ---------------------------------------------------------------------------
# CH-12 — Distribution immédiate prêteurs en mode source (Sinora §5.3).
# ---------------------------------------------------------------------------
@transaction.atomic
def distribute_interest_share_at_source(
    loan: Loan,
    payment,
) -> list[LenderInterestPayout]:
    """Distribue la part prêteurs des intérêts retenus à la source (T0).

    Activée uniquement si :
      • ``loan.mode_retenue_interets == "source"`` (CH-11),
      • le crédit a au moins une ``LenderAllocation``,
      • ``loan.interest_share_rate_fige`` > 0 (sinon kill-switch).

    Idempotent : si un ``LenderInterestPayout`` à T0 (installment=None) existe
    déjà pour ce crédit, on no-op. Évite les doubles versements en cas de
    rejeu du webhook ``decaissement`` ou d'auto-validate test.

    Calcul (montants identiques au flux LOT 9, mais sourcés sur
    ``loan.interets_retenus_source`` au lieu d'une imputation) :

        pretteurs_total = interets_retenus_source × share_rate_fige
        share(alloc)    = pretteurs_total × alloc.quote_part

    La dernière allocation absorbe le résidu d'arrondi pour que
    ``somme(payouts) == pretteurs_total``.
    """
    if loan.mode_retenue_interets != Loan.ModeRetenue.SOURCE:
        return []

    allocations = _allocations_for_loan(loan)
    if not allocations:
        # Crédit sans prêteurs internes — la coop garde 100 % des intérêts.
        return []

    interets_retenus = Decimal(loan.interets_retenus_source or "0")
    if interets_retenus <= 0:
        return []

    share_rate = Decimal(loan.interest_share_rate_fige or "0")
    if share_rate <= 0:
        return []

    # Idempotence : un payout T0 (installment=None) déjà posé pour ce crédit
    # signifie que la distribution a déjà eu lieu — on ne réexecute pas.
    already = (
        LenderInterestPayout.objects.filter(
            allocation__loan=loan,
            installment__isnull=True,
        )
        .exists()
    )
    if already:
        return list(
            LenderInterestPayout.objects.filter(
                allocation__loan=loan,
                installment__isnull=True,
            )
        )

    pretteurs_total = _q(interets_retenus * share_rate)
    if pretteurs_total <= 0:
        return []

    payouts: list[LenderInterestPayout] = []
    now = timezone.now()
    sum_dispatched = Decimal("0")
    for idx, alloc in enumerate(allocations):
        share = _q(pretteurs_total * Decimal(alloc.quote_part))
        if idx == len(allocations) - 1:
            share = _q(pretteurs_total - sum_dispatched)
        if share <= 0:
            continue
        payout = _credit_lender_at_source(
            allocation=alloc,
            payment=payment,
            montant=share,
            when=now,
        )
        payouts.append(payout)
        sum_dispatched += share

    record_audit(
        action="loan.interest_share_distributed_at_source",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "payment_id": payment.id,
            "interets_retenus_source": str(interets_retenus),
            "share_rate_fige": str(share_rate),
            "pretteurs_total": str(pretteurs_total),
            "payouts": [
                {
                    "allocation_id": p.allocation_id,
                    "lender_id": p.allocation.lender_id,
                    "montant": str(p.montant),
                }
                for p in payouts
            ],
        },
    )
    return payouts


def _credit_lender_at_source(
    *,
    allocation: LenderAllocation,
    payment,
    montant: Decimal,
    when,
) -> LenderInterestPayout:
    """Variante de ``_credit_lender`` pour les versements à T0 (sans échéance).

    Diffère uniquement par ``installment=None`` sur le ``LenderInterestPayout``
    et par l'événement émis (``lender.interest_paid_at_source``) qui porte
    une sémantique différente pour le destinataire ("ton placement a été
    utilisé pour financer un crédit, voici ta rémunération immédiate").
    """
    lender = allocation.lender
    account, _ = ClassicSavingsAccount.objects.select_for_update().get_or_create(
        member=lender,
        defaults={
            "solde": Decimal("0"),
            "date_ouverture": when.date(),
        },
    )
    nouveau_solde = Decimal(account.solde) + montant
    account.solde = nouveau_solde
    account.save(update_fields=["solde", "updated_at"])

    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.INTERET_PRETEUR,
        montant=montant,
        solde_apres=nouveau_solde,
        date=when,
    )

    payout = LenderInterestPayout.objects.create(
        allocation=allocation,
        installment=None,  # CH-12 — versement à T0, pas d'échéance attachée.
        payment=payment,
        montant=montant,
        date=when,
    )
    allocation.interest_share_paid_total = _q(
        Decimal(allocation.interest_share_paid_total) + montant
    )
    allocation.save(update_fields=["interest_share_paid_total", "updated_at"])

    # Notif au prêteur — il découvre que sa portion d'épargne placée a été
    # utilisée pour financer un crédit, et qu'il est rémunéré immédiatement.
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            "lender.interest_paid_at_source",
            member=lender,
            context={
                "prenom": lender.prenom,
                "montant": str(montant),
                "numero_dossier": allocation.loan.numero_dossier,
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning(
            "emit_event lender.interest_paid_at_source a échoué (payout=%s)",
            payout.id,
        )
    return payout
