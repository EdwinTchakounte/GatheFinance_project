"""Porte des frais d'étude (2026) — règlement + ouverture de l'instruction.

Règle : les frais d'étude sont **exigibles avant toute instruction**, et même
avant que l'avaliste soit sollicité. Une demande naît en ``EN_ATTENTE``
(« frais à payer ») et rien ne bouge tant qu'ils ne sont pas encaissés.

Trois canaux, **un seul au choix** (le montant est toujours réglé en une fois) :

  * **Agence** — cash-in admin (``Payment.Source.MANUEL``), existant.
  * **Mobile money** — ``/payments/init/`` (``Payment.Source.MOBILE_MONEY``),
    existant.
  * **Déduction épargne** — ``pay_study_fee_from_savings`` ci-dessous
    (``Payment.Source.DEDUCTION_EPARGNE``). Transfert interne : aucun
    encaissement à attendre, le Payment naît VALIDE.

Les trois convergent sur le même hook (``_hook_loan_request_fees``), qui est le
seul endroit qui décide de la suite du parcours.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import LoanRequest


logger = logging.getLogger(__name__)


class StudyFeeError(ValueError):
    """Le règlement des frais est impossible (motif lisible par le membre)."""


def study_fee_due(loan_request: LoanRequest) -> Decimal:
    """Montant des frais restant à payer pour cette demande. 0 = rien à payer."""
    from .services import study_fee_for

    if loan_request.frais_demande_credit_paye:
        return Decimal("0")
    return Decimal(study_fee_for(getattr(loan_request, "microcampaign", None)))


@transaction.atomic
def pay_study_fee_from_savings(loan_request: LoanRequest) -> "object":
    """Règle les frais d'étude en prélevant sur l'épargne **classique**.

    Renvoie le ``Payment`` créé (déjà VALIDE — le hook a donc déjà tourné et la
    demande a déjà quitté ``EN_ATTENTE``).

    Le prélèvement ne peut mordre que sur la part **réellement retirable**
    (``classic_withdrawable``) : ni le placement, ni l'épargne gelée en garantie
    ne peuvent servir à payer les frais — sinon on ponctionnerait un collatéral
    censé couvrir le crédit qu'on est justement en train d'instruire.

    On lit l'épargne classique et pas la collecte journalière : la collecte est
    reversée en fin de mois, la ponctionner casserait la clôture mensuelle.

    Lève ``StudyFeeError`` si les frais ne sont pas dus, s'il n'y a pas de
    compte classique, ou si le retirable est insuffisant.
    """
    from apps_coop.payments.models import Payment
    from apps_coop.savings.models import ClassicSavingsAccount, ClassicSavingsTransaction
    from apps_coop.savings.services import classic_withdrawable

    montant = study_fee_due(loan_request)
    if montant <= 0:
        raise StudyFeeError("Aucun frais d'étude n'est dû pour cette demande.")
    if loan_request.statut != LoanRequest.Statut.EN_ATTENTE:
        raise StudyFeeError(
            f"Cette demande n'attend pas de frais (statut : {loan_request.statut})."
        )

    member = loan_request.member
    account = (
        ClassicSavingsAccount.objects.select_for_update()
        .filter(member=member)
        .first()
    )
    if account is None:
        raise StudyFeeError(
            "Aucun compte d'épargne classique : choisis le paiement en agence "
            "ou par mobile money."
        )

    dispo = classic_withdrawable(account)
    if dispo < montant:
        raise StudyFeeError(
            f"Épargne disponible insuffisante : {dispo} XAF retirables pour "
            f"{montant} XAF de frais. Le placement et l'épargne gelée en "
            f"garantie ne sont pas ponctionnables."
        )

    now = timezone.now()
    account.solde = Decimal(account.solde) - montant
    account.save(update_fields=["solde", "updated_at"])

    payment = Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.FRAIS_DEMANDE_CREDIT,
        source=Payment.Source.DEDUCTION_EPARGNE,
        statut=Payment.Statut.VALIDE,
        date_versement=now,
        date_validation=now,
    )
    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.FRAIS_DEMANDE_CREDIT,
        montant=montant,
        solde_apres=account.solde,
        date=now,
    )

    record_audit(
        action="loan_request.study_fee_paid_from_savings",
        entite_type="LoanRequest",
        entite_id=loan_request.id,
        details={
            "payment_id": payment.id,
            "montant": str(montant),
            "solde_apres": str(account.solde),
        },
    )

    # Le Payment naît VALIDE : on déclenche nous-mêmes le hook métier, qui est
    # le point unique où la demande quitte EN_ATTENTE (les deux autres canaux y
    # arrivent via la validation du paiement).
    from apps_coop.payments.services import _hook_loan_request_fees

    _hook_loan_request_fees(payment, {})
    return payment


def open_instruction_after_fees(loan_request: LoanRequest) -> LoanRequest:
    """Suite du parcours une fois les frais encaissés. Point unique.

    « Frais d'abord, avaliste ensuite » : c'est ici, et seulement ici, que
    l'avaliste désigné à la soumission est réellement sollicité. Tant que les
    frais ne sont pas payés, aucun tiers n'est dérangé.

    Renvoie la demande. Ne lève pas : si l'avaliste est devenu invalide entre la
    soumission et le paiement (épargne retirée, compte suspendu), la demande
    reste en ``EN_ATTENTE_AVALISTE_INVALIDE``-like — concrètement on la laisse
    en EN_ATTENTE avec un motif, à charge de l'admin ou du membre de désigner un
    autre avaliste. On n'annule surtout pas des frais déjà encaissés dans un
    hook de paiement.
    """
    from .avaliste_services import request_avaliste_consent

    loan_request.frais_demande_credit_paye = True

    # Carnet obligatoire (bénéficiaire campagne) : les frais d'étude sont payés,
    # mais tant que le carnet n'est pas réglé/créé la demande RESTE en attente.
    # L'instruction s'ouvrira à la validation du paiement carnet (cf.
    # ``payments.services._hook_carnet_fees`` qui rappelle cette fonction).
    from .services import campaign_member_needs_carnet

    if campaign_member_needs_carnet(loan_request.member):
        loan_request.save(
            update_fields=["frais_demande_credit_paye", "updated_at"]
        )
        record_audit(
            action="loan_request.awaiting_carnet",
            entite_type="LoanRequest",
            entite_id=loan_request.id,
            details={"member_id": loan_request.member_id},
        )
        return loan_request

    numero = (loan_request.avaliste_numero_saisi or "").strip()
    nom = (loan_request.avaliste_nom_saisi or "").strip()

    if not numero:
        loan_request.statut = LoanRequest.Statut.EN_INSTRUCTION
        loan_request.save(
            update_fields=["frais_demande_credit_paye", "statut", "updated_at"]
        )
        return loan_request

    # Voie avaliste : on sollicite maintenant. request_avaliste_consent pose
    # lui-même le statut (EN_ATTENTE_AVALISTE) et le gel du demandeur.
    loan_request.save(update_fields=["frais_demande_credit_paye", "updated_at"])
    try:
        request_avaliste_consent(
            loan_request, numero_identification=numero, nom=nom
        )
    except (ValueError, LookupError) as exc:
        # L'avaliste validé à la soumission ne l'est plus. Les frais sont
        # encaissés, on ne les rembourse pas ici : la demande reste en attente
        # d'une nouvelle désignation.
        logger.warning(
            "LoanRequest #%s : frais encaissés mais l'avaliste %r est devenu "
            "invalide (%s). Demande laissée en EN_ATTENTE.",
            loan_request.id,
            numero,
            exc,
        )
        loan_request.motif_rejet = (
            f"Avaliste indisponible au moment de l'instruction : {exc} "
            f"Désigne un autre avaliste."
        )
        loan_request.save(update_fields=["motif_rejet", "updated_at"])
        record_audit(
            action="loan_request.avaliste_invalid_after_fees",
            entite_type="LoanRequest",
            entite_id=loan_request.id,
            details={"avaliste_numero": numero, "erreur": str(exc)},
        )
        return loan_request

    loan_request.avaliste_numero_saisi = ""
    loan_request.avaliste_nom_saisi = ""
    loan_request.save(
        update_fields=["avaliste_numero_saisi", "avaliste_nom_saisi", "updated_at"]
    )
    return loan_request
