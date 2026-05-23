"""Scheduled tasks for the savings domain.

Wired by ``apps_coop.audit.management.commands.seed_q_schedules`` to run via
django-q2's qcluster worker.

Le cron ``savings.interest.monthly`` tourne le 1er de chaque mois à 02h00.
Algorithme (idempotent par mois) :

    pour chaque SavingsAccount où solde >= MIN_BALANCE_FOR_INTEREST :
        si déjà un SavingsTransaction(INTERET) ce mois → skip
        crédit = solde × 0.01           (Article 4 — 1 %/mois)
        solde += crédit  (verrouillé via select_for_update)
        SavingsTransaction(type=INTERET, montant=crédit, payment=None) ← traçabilité
        audit + email
"""
from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .cutoff import MIN_BALANCE_FOR_INTEREST


logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def crediter_interets_mensuels() -> dict:
    """Crédite le taux d'épargne mensuel sur chaque compte d'épargne actif.

    Le taux est lu depuis ``RateParam.SAVINGS_INTEREST_MONTHLY`` (modifiable
    côté admin, BR2) avec fallback sur le défaut réglementaire (1 %, Article 4).
    Idempotent : ne crédite pas 2× le même mois pour un compte donné.
    """
    from apps_coop.members.models import Member
    from apps_coop.notifications.services import send_template
    from apps_coop.payments.models import RateParam
    from apps_coop.payments.rates import get_rate
    from apps_coop.savings.models import SavingsAccount, SavingsTransaction

    now = timezone.now()
    period = f"{now.year}-{now.month:02d}"
    taux = get_rate(RateParam.Code.SAVINGS_INTEREST_MONTHLY)

    comptes_traites = 0
    comptes_ignores = 0
    erreurs = 0
    total_credite = Decimal("0")

    # On itère seulement sur les comptes de membres actifs — un compte suspendu
    # n'accumule pas d'épargne dans la logique de la coop.
    qs = (
        SavingsAccount.objects
        .filter(member__statut=Member.Statut.ACTIF)
        .select_related("member", "member__user")
    )

    for account in qs:
        try:
            with transaction.atomic():
                # Verrou ligne — sérialise vis-à-vis des dépôts concurrents.
                locked = (
                    SavingsAccount.objects
                    .select_for_update()
                    .get(pk=account.pk)
                )

                # Idempotence : un seul INTERET par mois calendaire.
                already_credited_this_month = SavingsTransaction.objects.filter(
                    account=locked,
                    type_op=SavingsTransaction.TypeOp.INTERET,
                    date__year=now.year,
                    date__month=now.month,
                ).exists()
                if already_credited_this_month:
                    comptes_ignores += 1
                    continue

                solde = Decimal(locked.solde)
                if solde < MIN_BALANCE_FOR_INTEREST:
                    comptes_ignores += 1
                    continue

                interets = _q(solde * taux)
                if interets <= 0:
                    comptes_ignores += 1
                    continue

                nouveau_solde = _q(solde + interets)
                locked.solde = nouveau_solde
                locked.save(update_fields=["solde", "updated_at"])

                SavingsTransaction.objects.create(
                    account=locked,
                    payment=None,  # crédit système, pas un Payment
                    type_op=SavingsTransaction.TypeOp.INTERET,
                    montant=interets,
                    solde_apres=nouveau_solde,
                    date=now,
                )

                record_audit(
                    action="savings.interest_credited",
                    entite_type="SavingsAccount",
                    entite_id=locked.pk,
                    details={
                        "member_id": locked.member_id,
                        "period": period,
                        "rate": str(taux),
                        "solde_avant": str(solde),
                        "interets": str(interets),
                        "solde_apres": str(nouveau_solde),
                    },
                )

                comptes_traites += 1
                total_credite += interets

            # Email hors transaction — l'échec d'envoi ne doit pas rollback.
            member = account.member
            if getattr(member.user, "email", None):
                try:
                    send_template(
                        "savings.interest_credited",
                        to=member.user.email,
                        member=member,
                        context={
                            "prenom": member.prenom,
                            "period": period,
                            "interets": f"{int(interets):,}".replace(",", " "),
                            "solde_apres": f"{int(nouveau_solde):,}".replace(",", " "),
                        },
                    )
                except Exception:  # noqa: BLE001
                    # Le template peut ne pas exister encore — on n'échoue pas le cron.
                    logger.warning("savings.interest_credited email skipped", exc_info=True)

        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception(
                "crediter_interets_mensuels — échec sur account_id=%s", account.pk
            )

    summary = {
        "period": period,
        "rate": str(taux),
        "comptes_traites": comptes_traites,
        "comptes_ignores": comptes_ignores,
        "erreurs": erreurs,
        "total_credite": str(total_credite),
    }
    record_audit(
        action="cron.savings_interest.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("crediter_interets_mensuels summary=%s", summary)
    return summary
