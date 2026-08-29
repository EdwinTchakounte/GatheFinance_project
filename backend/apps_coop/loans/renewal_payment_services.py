"""Encaissement des intérêts de reconduction.

Les intérêts de reconduction (taux × capital restant, taux piloté par l'admin)
sont réglables **quand le membre veut** : avant la décision du comité ou après.
Jusqu'ici ce versement n'existait nulle part — aucun montant n'était persisté
et aucun canal de paiement n'acceptait le type ``frais_reconduction``. Le
membre lisait « tu verses les intérêts maintenant » sans jamais pouvoir payer.

S'ils sont encaissés avant l'approbation, ils ne sont pas réintégrés dans
l'échéancier du nouveau dossier ; sinon ils y sont reportés.

Trois canaux, comme pour les frais d'étude :

  * **prélèvement sur épargne** — ``pay_renewal_interest_from_savings`` ci-dessous ;
  * **mobile money** — ``POST /payments/init/`` type ``frais_reconduction`` ;
  * **espèces en agence** — cash-in admin.

Les deux derniers convergent vers ``mark_renewal_interest_paid``, appelé par
le hook métier à la validation du paiement.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder

from .models import LoanRenewal

logger = logging.getLogger(__name__)


class RenewalPaymentError(ValueError):
    """Le règlement des intérêts est impossible (motif lisible par le membre)."""


def renewal_interest_due(renewal: LoanRenewal) -> Decimal:
    """Reste à verser sur cette reconduction. 0 = rien à payer."""
    return Decimal(renewal.reste_a_payer)


def _open_renewal_for(payment) -> LoanRenewal | None:
    """Reconduction en attente d'encaissement pour le membre d'un paiement."""
    # Ni le statut ni le mode ne filtrent : le versement est libre — il peut
    # arriver avant la décision comme après (reconduction déjà approuvée).
    return (
        LoanRenewal.objects.select_for_update()
        .filter(
            loan__member=payment.member,
            interets_payes_at__isnull=True,
            interets_dus__gt=0,
        )
        .exclude(statut=LoanRenewal.Statut.REJETEE)
        .order_by("date_demande")
        .first()
    )


@transaction.atomic
def mark_renewal_interest_paid(renewal: LoanRenewal, payment) -> LoanRenewal:
    """Constate l'encaissement des intérêts de reconduction. Idempotent."""
    if renewal.interets_payes_at is not None:
        return renewal

    renewal.interets_payes_at = timezone.now()
    renewal.frais_reconduction_payment = payment
    renewal.save(
        update_fields=[
            "interets_payes_at",
            "frais_reconduction_payment",
            "updated_at",
        ]
    )
    record_audit(
        action="loan_renewal.interest_paid",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        details={
            "payment_id": getattr(payment, "id", None),
            "montant": str(renewal.interets_dus),
            "loan_id": renewal.loan_id,
        },
    )
    return renewal


@transaction.atomic
def pay_renewal_interest_from_savings(renewal: LoanRenewal) -> "object":
    """Prélève les intérêts de reconduction sur l'épargne **classique**.

    Renvoie le ``Payment`` créé (déjà VALIDE). Comme pour les frais d'étude, on
    ne mord que sur la part réellement retirable : ni le placement ni l'épargne
    gelée en garantie ne sont ponctionnables — ce serait entamer un collatéral.
    """
    from apps_coop.payments.models import Payment
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )
    from apps_coop.savings.services import classic_withdrawable

    if renewal.statut == LoanRenewal.Statut.REJETEE:
        raise RenewalPaymentError(
            "Cette reconduction a été rejetée : aucun versement n'est attendu."
        )
    montant = renewal_interest_due(renewal)
    if montant <= 0:
        raise RenewalPaymentError(
            "Aucun intérêt n'est dû pour cette reconduction."
        )

    member = renewal.loan.member
    account = (
        ClassicSavingsAccount.objects.select_for_update()
        .filter(member=member)
        .first()
    )
    if account is None:
        raise RenewalPaymentError(
            "Aucun compte d'épargne classique : choisis le paiement en agence "
            "ou par mobile money."
        )

    dispo = classic_withdrawable(account)
    if dispo < montant:
        raise RenewalPaymentError(
            f"Épargne disponible insuffisante : {dispo} XAF retirables pour "
            f"{montant} XAF d'intérêts. Le placement et l'épargne gelée en "
            f"garantie ne sont pas ponctionnables."
        )

    now = timezone.now()
    account.solde = Decimal(account.solde) - montant
    account.save(update_fields=["solde", "updated_at"])

    payment = Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.FRAIS_RECONDUCTION,
        source=Payment.Source.DEDUCTION_EPARGNE,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )
    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.INTERETS_RECONDUCTION,
        montant=montant,
        solde_apres=account.solde,
        date=now,
        booklet_order=BookletOrder.latest_for(account.member),
    )

    record_audit(
        action="loan_renewal.interest_paid_from_savings",
        entite_type="LoanRenewal",
        entite_id=renewal.id,
        details={
            "payment_id": payment.id,
            "montant": str(montant),
            "solde_apres": str(account.solde),
        },
    )

    # Le Payment naît VALIDE : on constate nous-mêmes l'encaissement (les deux
    # autres canaux y arrivent via le hook de validation du paiement).
    mark_renewal_interest_paid(renewal, payment)
    return payment


def hook_renewal_interest(payment, meta: dict | None = None) -> None:
    """Hook métier ``frais_reconduction`` — appelé à la validation du paiement.

    Rattache le versement à la reconduction en attente du membre. Sans
    reconduction ouverte, on ne fait rien (paiement isolé, tracé mais inerte)
    plutôt que de lever : un hook ne doit jamais casser un encaissement déjà
    constaté.
    """
    renewal = _open_renewal_for(payment)
    if renewal is None:
        logger.warning(
            "Paiement frais_reconduction #%s : aucune reconduction en attente "
            "pour le membre %s — versement laissé sans rattachement.",
            getattr(payment, "id", None),
            getattr(payment.member, "numero_membre", payment.member_id),
        )
        return
    mark_renewal_interest_paid(renewal, payment)
