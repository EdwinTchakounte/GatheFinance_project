"""Rémunération prêteur des intérêts crédit (refonte 2026 §7.5, révisée 2026-07-24).

Exporté pour ``apps_coop.payments.services._hook_loan_repayment`` qui pose les
``LoanRepayment`` puis appelle ``distribute_interest_share`` pour chaque
imputation (mode échéances). Le mode « à la source » passe par
``distribute_interest_share_at_source`` au décaissement. Aussi exporté pour le
helper de clôture ``release_loan_tranches`` (toutes échéances PAYEE).

Contrat de l'API (idempotence + sûreté) :
  * ``distribute_interest_share`` n'agit que sur les imputations dont la
    portion intérêt > 0. La portion intérêt est calculée en priorité avant
    le capital, et bornée par les intérêts restants dus.
  * Le crédit du compte épargne classique du prêteur est *append-only* :
    ``ClassicSavingsTransaction(INTERET_PRETEUR)`` + ``solde_apres`` figé.
  * ``release_loan_tranches`` ne libère que les tranches ENGAGEE — toute
    réexécution est un no-op (idempotent).

Règle unique 2026-07-24 : chaque prêteur touche ``k × sa contribution``
(``k`` = AppSetting ``loans.lender.interest_rate``, éditable admin, défaut 0.03)
dans les DEUX modes. En mode échéances la cible est répartie au prorata de
l'intérêt payé (cumul borné par ``interest_share_paid_total``) ; en mode source
elle est versée en une fois au décaissement. ``k <= 0`` = kill-switch.
L'ancien ``lender.interest_share_rate`` (partage 50/50 par quote-part) est
abandonné.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import get_str_setting, record as record_audit
from apps_coop.portal_urls import portal_url
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


def _lender_rate() -> Decimal:
    """Lit ``loans.lender.interest_rate`` (k) en Decimal sûr, clampé [0,1].

    Règle unique 2026-07-24 : chaque prêteur touche ``k × sa contribution``,
    dans les deux modes (à la source ET aux échéances). ``k <= 0`` = kill-switch
    (aucune rémunération prêteur). Remplace l'ancien ``lender.interest_share_rate``
    (partage 50/50 par quote-part), devenu legacy.
    """
    raw = get_str_setting("loans.lender.interest_rate", "0.03")
    try:
        rate = Decimal(str(raw).strip())
    except Exception:  # noqa: BLE001 — admin a mis n'importe quoi
        logger.warning(
            "loans.lender.interest_rate invalide (%r), fallback 0.03", raw
        )
        rate = Decimal("0.03")
    if rate < 0 or rate > 1:
        logger.warning(
            "loans.lender.interest_rate hors [0,1] (%s), clamp", rate
        )
        rate = max(Decimal("0"), min(Decimal("1"), rate))
    return rate


def _allocations_for_loan(loan: Loan) -> list[LenderAllocation]:
    """Allocations prêteurs ACTIVES du crédit (vide si crédit legacy).

    Exclut les allocations restituées par apport : le prêteur a déjà été fait
    entièrement (capital + intérêts placement), la coop a repris le risque et
    garde donc sa quote-part des intérêts des remboursements futurs.
    """
    return list(
        LenderAllocation.objects.select_for_update()
        .filter(loan=loan, restitue_par_apport=False)
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

    Règle unique 2026-07-24 : chaque prêteur touche ``k × sa contribution``
    (``k`` = ``loans.lender.interest_rate``), réparti AU PRORATA de l'intérêt
    payé à chaque imputation → cumul = ``k × montant_alloue`` sur toute la vie
    du crédit (même total que le mode « à la source »). Le cumul est borné par
    ``interest_share_paid_total`` : jamais de surpaiement.

    No-op (retourne ``[]``) si :
      • le crédit n'a aucune ``LenderAllocation`` (crédit legacy pré-LOT 7),
      • la portion intérêt de l'imputation est nulle,
      • l'intérêt total du crédit est nul,
      • ``k <= 0`` (kill-switch), ou chaque prêteur a déjà atteint sa cible.
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

    k_rate = _lender_rate()
    if k_rate <= 0:
        return []

    # Intérêt total du crédit (somme des échéances). Sert à répartir la
    # rémunération cible « k × contribution » AU PRORATA de l'intérêt
    # effectivement payé à chaque imputation : sur toute la vie du crédit,
    # chaque prêteur touche donc k × montant_alloue — identique au mode « à la
    # source ». (Ancienne règle : quote_part × interest_share_rate × intérêt.)
    interet_total_loan = sum(
        (Decimal(i.montant_interets) for i in loan.installments.all()),
        Decimal("0"),
    )
    if interet_total_loan <= 0:
        return []

    payouts: list[LenderInterestPayout] = []
    now = timezone.now()
    for alloc in allocations:
        cible_totale = _q(k_rate * Decimal(alloc.montant_alloue))
        reste = cible_totale - Decimal(alloc.interest_share_paid_total)
        if reste <= 0:
            # Prêteur déjà rémunéré à hauteur de k × sa contribution.
            continue
        # Part de cette imputation = cible × (intérêt payé / intérêt total),
        # bornée par le reste dû (jamais de surpaiement ; l'arrondi favorise
        # la coop, jamais le prêteur).
        share = _q(cible_totale * interet_imputation / interet_total_loan)
        share = min(share, reste)
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
            "interet_total_loan": str(interet_total_loan),
            "lender_interest_rate": str(k_rate),
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

    # Notif prêteur : « ta part est de nouveau disponible ». On agrège le
    # montant libéré par prêteur (un même prêteur peut avoir plusieurs tranches
    # sur ce crédit) et on envoie après commit (best-effort).
    from collections import defaultdict

    per_member: dict = defaultdict(Decimal)
    member_by_id: dict = {}
    for t in engaged:
        per_member[t.member_id] += Decimal(t.montant)
        member_by_id[t.member_id] = t.member

    def _notify_lenders() -> None:
        from django.conf import settings

        from apps_coop.notifications.events import emit_event

        for mid, montant in per_member.items():
            m = member_by_id.get(mid)
            if m is None:
                continue
            try:
                emit_event(
                    "lender.tranche_released",
                    member=m,
                    context={
                        "prenom": m.prenom,
                        "montant": f"{int(montant):,}".replace(",", " "),
                        "numero_dossier": loan.numero_dossier,
                        "portal_url": portal_url(),
                    },
                )
            except Exception:  # pragma: no cover — notif best-effort
                logger.exception("notif tranche libérée prêteur a échoué")

    transaction.on_commit(_notify_lenders)
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
      • ``interets_retenus_source`` > 0,
      • ``k`` (``loans.lender.interest_rate``) > 0 (sinon kill-switch).

    Idempotent : si un ``LenderInterestPayout`` à T0 (installment=None) existe
    déjà pour ce crédit, on no-op. Évite les doubles versements en cas de
    rejeu du webhook ``decaissement`` ou d'auto-validate test.

    Calcul (règle 2026-07-24) : chaque prêteur touche ``k`` % de SA contribution.

        share(alloc) = k × alloc.montant_alloue

    où ``k`` = AppSetting ``loans.lender.interest_rate`` (éditable par l'admin),
    lu en direct au décaissement. Ex. k=10 %, contribution 10 000 → 1 000.

    Remplace l'ancienne règle « part = quote_part × (intérêts_source × 0.5) »
    qui, avec un prêteur unique (résidu absorbé), lui faisait toucher 50 % de
    TOUT l'intérêt du crédit quelle que soit la fraction réellement financée.
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

    # k = taux d'intérêt prêteur, réglage admin dédié (éditable), lu en direct.
    k_rate = _lender_rate()
    if k_rate <= 0:
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

    payouts: list[LenderInterestPayout] = []
    now = timezone.now()
    total_credite = Decimal("0")
    for alloc in allocations:
        # Chaque prêteur touche k % de SA contribution (montant_alloue) —
        # indépendant des autres et de la fraction financée par la coop.
        share = _q(k_rate * Decimal(alloc.montant_alloue))
        if share <= 0:
            continue
        payout = _credit_lender_at_source(
            allocation=alloc,
            payment=payment,
            montant=share,
            when=now,
        )
        payouts.append(payout)
        total_credite += share

    record_audit(
        action="loan.interest_share_distributed_at_source",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "payment_id": payment.id,
            "interets_retenus_source": str(interets_retenus),
            "lender_interest_rate": str(k_rate),
            "total_credite_pretteurs": str(total_credite),
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
