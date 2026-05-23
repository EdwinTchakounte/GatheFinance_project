"""Business hooks fired when a Payment transitions to ``valide``.

The webhook view stays thin: it authenticates, locks the Payment row, sets
``statut=valide`` and delegates the rest here. Each Payment.type maps to a
handler — handlers that aren't implemented yet raise NotImplementedError so
the system fails loud rather than silently miss a side effect.

Every handler MUST be idempotent: it can be called more than once for the
same Payment (the webhook may replay, or the cron may re-trigger after a
network blip). Use ``Payment.statut`` and timestamps as guards.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit


def _fmt_xaf(amount) -> str:
    """Pretty-print a Decimal/int as `1 234 567`."""
    try:
        return f"{int(amount):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(amount)

from .models import Payment
from .providers import get_provider


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def init_payin_for_payment(
    payment: Payment,
    *,
    phone: str,
    network: str,
) -> tuple[str | None, str]:
    """Push a payin request to the configured provider.

    Returns ``(payment_url, provider_reference)``. The Payment row is updated
    in place with ``reference_externe`` and ``gateway_initiated_at`` — the
    caller (view) is expected to persist it.
    """
    provider = get_provider(payment.provider_code or "tara")
    result = provider.init_payin(payment, phone=phone, network=network)
    payment.reference_externe = result.provider_reference
    payment.gateway_initiated_at = timezone.now()
    return result.payment_url, result.provider_reference


@transaction.atomic
def handle_webhook_event(
    payment_idempotency_key: str | uuid.UUID,
    new_status: str,
    *,
    provider_reference: str = "",
    raw_payload: dict | None = None,
) -> Payment:
    """Apply a verified webhook event to the matching Payment row.

    Idempotent: replaying the same event is a no-op. Returns the updated
    (or unchanged) Payment row.

    Raises ``Payment.DoesNotExist`` if the key is unknown — the caller view
    should return 404 to the provider so it stops retrying for ghost rows.
    """
    payment = Payment.objects.select_for_update().get(idempotency_key=payment_idempotency_key)

    # Already-final terminal states are not re-evaluated.
    if payment.statut == Payment.Statut.VALIDE:
        return payment
    if payment.statut == Payment.Statut.REJETE and new_status != "valide":
        return payment

    if new_status == "valide":
        return _confirm(payment, provider_reference=provider_reference, raw=raw_payload or {})
    if new_status == "rejete":
        return _reject(payment, raw=raw_payload or {})
    # "en_attente" — provider says "still pending", nothing to change yet.
    return payment


# ---------------------------------------------------------------------------
# Private — confirmation pipeline
# ---------------------------------------------------------------------------


def _confirm(payment: Payment, *, provider_reference: str, raw: dict) -> Payment:
    payment.statut = Payment.Statut.VALIDE
    payment.date_validation = timezone.now()
    if provider_reference:
        payment.reference_externe = provider_reference
    payment.save(update_fields=["statut", "date_validation", "reference_externe", "updated_at"])

    record_audit(
        action="payment.confirmed",
        entite_type="Payment",
        entite_id=payment.id,
        details={
            "type": payment.type,
            "montant": str(payment.montant),
            "provider": payment.provider_code,
            "reference": payment.reference_externe,
        },
    )

    handler = _BUSINESS_HOOKS.get(payment.type)
    if handler is None:
        logger.warning(
            "No business handler registered for Payment.type=%s (id=%s)",
            payment.type,
            payment.id,
        )
    else:
        handler(payment, raw)
    return payment


def _reject(payment: Payment, *, raw: dict) -> Payment:
    payment.statut = Payment.Statut.REJETE
    payment.motif_rejet = (raw.get("message") or raw.get("reason") or "Rejected by provider")[:500]
    payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
    record_audit(
        action="payment.rejected",
        entite_type="Payment",
        entite_id=payment.id,
        details={"reason": payment.motif_rejet, "provider": payment.provider_code},
    )
    return payment


# ---------------------------------------------------------------------------
# Business hooks per Payment.type
# ---------------------------------------------------------------------------
# Each hook receives the freshly-confirmed Payment and the raw provider
# payload. It must be idempotent and may NOT raise — log + record_audit on
# failure rather than blow up the webhook.


def _hook_adhesion(payment: Payment, _raw: dict) -> None:
    """UC1 — 1re cotisation reçue → activate the Member."""
    from apps_coop.members.models import Member  # local import to avoid cycles
    from apps_coop.notifications.services import send_template

    member = payment.member
    if member.statut == Member.Statut.ACTIF:
        return
    member.statut = Member.Statut.ACTIF
    member.save(update_fields=["statut", "updated_at"])
    record_audit(
        action="member.activated",
        entite_type="Member",
        entite_id=member.id,
        details={"trigger": "payment.frais_adhesion", "payment_id": payment.id},
    )
    send_template(
        "member.activated",
        to=member.user.email,
        member=member,
        context={
            "prenom": member.prenom,
            "numero_membre": member.numero_membre,
            "montant": _fmt_xaf(payment.montant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_savings_deposit(payment: Payment, _raw: dict) -> None:
    """UC2 — épargne validée → crédite le SavingsAccount + crée la SavingsTransaction.

    Atomique et idempotent : tourné dans la transaction de
    ``handle_webhook_event``. Race conditions entre dépôts concurrents
    résolues par ``select_for_update`` sur le SavingsAccount.

    Règlement, Article 4 : si le versement est validé après 17h00 (ou un
    week-end), il est compté à la **date de valeur** du prochain jour ouvré.
    L'horodatage du paiement reste inchangé pour la traçabilité (champ
    ``payment.date_validation``) ; seule ``SavingsTransaction.date`` reflète
    la date métier de l'opération.

    Architecture validée : voir ``architecture/03-depot-epargne.md``.
    """
    from datetime import datetime, time

    from apps_coop.savings.cutoff import compute_value_date
    from apps_coop.savings.models import SavingsAccount, SavingsTransaction

    # Verrou ligne sur le compte du membre — sérialise les dépôts simultanés.
    account = SavingsAccount.objects.select_for_update().get(member=payment.member)

    nouveau_solde = account.solde + payment.montant
    account.solde = nouveau_solde
    account.save(update_fields=["solde", "updated_at"])

    instant = payment.date_validation or timezone.now()
    value_date = compute_value_date(instant)
    # Le timestamp de la transaction reflète la date de valeur : on ré-aligne
    # le ``date`` à 17h00 du jour ouvré applicable. L'horodatage exact reste
    # disponible via ``payment.date_validation`` pour audit.
    valued_at = datetime.combine(value_date, time(17, 0)).replace(tzinfo=instant.tzinfo)
    deferred = value_date != instant.date()

    transaction_row = SavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=SavingsTransaction.TypeOp.DEPOT,
        montant=payment.montant,
        solde_apres=nouveau_solde,
        date=valued_at,
    )

    record_audit(
        action="savings.deposit",
        entite_type="SavingsTransaction",
        entite_id=transaction_row.id,
        details={
            "member_id": payment.member_id,
            "account_id": account.id,
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "solde_apres": str(nouveau_solde),
            "deferred_to_next_business_day": deferred,
            "value_date": value_date.isoformat(),
        },
    )
    from apps_coop.notifications.services import send_template

    send_template(
        "savings.deposit_confirmed",
        to=payment.member.user.email,
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "montant": _fmt_xaf(payment.montant),
            "solde_apres": _fmt_xaf(nouveau_solde),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_classic_savings_deposit(payment: Payment, _raw: dict) -> None:
    """Dépôt validé sur le compte **épargne classique** (dissocié de la cotisation).

    Atomique + idempotent (tourné dans la transaction de ``handle_webhook_event``).
    Pas de règle de cut-off ici : c'est de l'épargne libre, pas la collecte
    journalière. Le compte est créé à la volée au premier dépôt.
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    # Création paresseuse puis verrou ligne pour sérialiser les dépôts concurrents.
    ClassicSavingsAccount.objects.get_or_create(
        member=payment.member,
        defaults={"date_ouverture": timezone.localdate()},
    )
    account = ClassicSavingsAccount.objects.select_for_update().get(member=payment.member)

    nouveau_solde = account.solde + payment.montant
    account.solde = nouveau_solde
    account.save(update_fields=["solde", "updated_at"])

    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        montant=payment.montant,
        solde_apres=nouveau_solde,
        date=payment.date_validation or timezone.now(),
    )

    record_audit(
        action="classic_savings.deposit",
        entite_type="ClassicSavingsAccount",
        entite_id=account.id,
        details={
            "member_id": payment.member_id,
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "solde_apres": str(nouveau_solde),
        },
    )


def _hook_loan_repayment(payment: Payment, _raw: dict) -> None:
    """UC3 step C — remboursement validé → imputation FIFO sur les échéances.

    Algorithme (cf. ``architecture/06-remboursement-echeance.md``) :
      reste = Payment.montant
      pour chaque LoanInstallment non payée, ordre croissant date_echeance :
          du = montant_total - montant_paye
          impute = min(reste, du)
          LoanRepayment.create(installment, payment, impute)
          installment.montant_paye += impute
          statut = payee si soldée, partielle sinon
          reste -= impute
          break si reste == 0

    Side effects :
      - Loan.solde_restant -= Payment.montant (en pratique : -= imputé total)
      - Si toutes les installments == payee → Loan.statut = cloture
      - Sinon si plus aucune en_retard → Loan.statut = actif (sortie de retard)
    """
    from decimal import Decimal

    from apps_coop.loans.models import Loan, LoanInstallment, LoanRepayment

    if payment.loan_id is None:
        logger.error(
            "Payment #%s (remboursement) sans loan_id — impossible d'imputer.",
            payment.id,
        )
        return

    loan = Loan.objects.select_for_update().get(pk=payment.loan_id)
    installments = list(
        LoanInstallment.objects.select_for_update()
        .filter(loan=loan)
        .exclude(statut=LoanInstallment.Statut.PAYEE)
        .order_by("date_echeance", "numero_echeance")
    )

    reste = Decimal(payment.montant)
    impacted = []
    for inst in installments:
        if reste <= 0:
            break
        # Le dû inclut la pénalité Article 12 (si posée) : capital + intérêts
        # + pénalité. L'échéance n'est soldée que pénalité comprise.
        du_total = Decimal(inst.montant_total) + Decimal(inst.montant_penalite)
        du = du_total - Decimal(inst.montant_paye)
        if du <= 0:
            continue
        impute = du if reste >= du else reste
        LoanRepayment.objects.create(
            installment=inst,
            payment=payment,
            montant_impute=impute,
            date=payment.date_validation or timezone.now(),
        )
        inst.montant_paye = Decimal(inst.montant_paye) + impute
        if Decimal(inst.montant_paye) >= du_total:
            inst.statut = LoanInstallment.Statut.PAYEE
        else:
            inst.statut = LoanInstallment.Statut.PARTIELLE
        inst.save(update_fields=["montant_paye", "statut", "updated_at"])
        impacted.append({"installment": inst.numero_echeance, "impute": str(impute), "statut": inst.statut})
        reste -= impute

    impute_total = Decimal(payment.montant) - reste
    loan.solde_restant = max(Decimal(loan.solde_restant) - impute_total, Decimal("0"))

    all_installments = LoanInstallment.objects.filter(loan=loan)
    all_paid = not all_installments.exclude(statut=LoanInstallment.Statut.PAYEE).exists()
    any_late = all_installments.filter(statut=LoanInstallment.Statut.EN_RETARD).exists()

    if all_paid:
        loan.statut = Loan.Statut.CLOTURE
    elif loan.statut == Loan.Statut.EN_RETARD and not any_late:
        loan.statut = Loan.Statut.ACTIF

    loan.save(update_fields=["solde_restant", "statut", "updated_at"])

    record_audit(
        action="loan.repayment",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "imputations": impacted,
            "new_solde_restant": str(loan.solde_restant),
            "new_statut": loan.statut,
        },
    )
    from apps_coop.notifications.services import send_template

    send_template(
        "loan.repayment_confirmed",
        to=payment.member.user.email,
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "montant": _fmt_xaf(payment.montant),
            "numero_dossier": loan.numero_dossier,
            "solde_restant": _fmt_xaf(loan.solde_restant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_loan_request_fees(payment: Payment, _raw: dict) -> None:
    """UC3 step A — frais de dossier réglés → la LoanRequest la plus récente
    en ``en_attente`` du membre passe en ``en_instruction``.

    Le rapprochement est fait par (membre, statut=en_attente) parce qu'au
    moment de l'init paiement on n'a pas créé de FK direct (un membre ne peut
    avoir qu'une seule demande en attente à la fois, garanti par la règle
    d'éligibilité — cf. ``compute_eligibility``).
    """
    from apps_coop.loans.models import LoanRequest  # local — avoid cycles

    pending = (
        LoanRequest.objects.select_for_update()
        .filter(member=payment.member, statut=LoanRequest.Statut.EN_ATTENTE)
        .order_by("-date_soumission")
        .first()
    )
    if pending is None:
        logger.warning(
            "Payment #%s (frais_demande_credit) validé mais aucune LoanRequest "
            "en_attente trouvée pour le membre %s — webhook orphelin ?",
            payment.id,
            payment.member_id,
        )
        return

    pending.statut = LoanRequest.Statut.EN_INSTRUCTION
    pending.save(update_fields=["statut", "updated_at"])
    record_audit(
        action="loan_request.fees_paid",
        entite_type="LoanRequest",
        entite_id=pending.id,
        details={
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "new_statut": pending.statut,
        },
    )
    from apps_coop.notifications.services import send_template

    send_template(
        "loan_request.fees_paid",
        to=payment.member.user.email,
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "request_id": pending.id,
            "montant": _fmt_xaf(payment.montant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_carnet_fees(payment: Payment, _raw: dict) -> None:
    """Frais de carnet réglés → enregistre une `BookletOrder` (statut `payee`).

    L'agence imprime ensuite le carnet et change le statut depuis le Django
    admin. Idempotent : si une `BookletOrder` existe déjà pour ce Payment, on
    no-op (le webhook Tara peut rejouer).
    """
    from apps_coop.members.models import BookletOrder

    order, created = BookletOrder.objects.get_or_create(
        payment=payment,
        defaults={
            "member": payment.member,
            "statut": BookletOrder.Statut.PAYEE,
        },
    )
    record_audit(
        action="booklet.ordered",
        entite_type="BookletOrder",
        entite_id=order.id,
        details={
            "member_id": payment.member_id,
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "created": created,
        },
    )
    if not created:
        # Replay du webhook — ne renvoie pas un 2e email.
        return

    from apps_coop.notifications.services import send_template

    send_template(
        "booklet.ordered",
        to=payment.member.user.email,
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "numero_membre": payment.member.numero_membre,
            "montant": _fmt_xaf(payment.montant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_decaissement(payment: Payment, _raw: dict) -> None:
    """Décaissement validé (payout Tara confirmé) → met le Loan en `actif`
    + date_decaissement = aujourd'hui.

    Pré-condition : ``payment.loan_id`` est rempli au moment de l'init payout
    par l'admin (cf. `loans.services.disburse_loan_via_tara`). L'idempotence
    contre les rejeux est assurée par ``handle_webhook_event`` (le même
    Payment ne déclenche pas 2× le hook).
    """
    from apps_coop.loans.models import Loan

    if payment.loan_id is None:
        logger.error(
            "Payment #%s (decaissement) sans loan_id — impossible de marquer le crédit.",
            payment.id,
        )
        return

    loan = Loan.objects.select_for_update().get(pk=payment.loan_id)
    loan.date_decaissement = timezone.now().date()
    loan.statut = Loan.Statut.ACTIF
    loan.save(update_fields=["date_decaissement", "statut", "updated_at"])

    record_audit(
        action="loan.disbursed",
        entite_type="Loan",
        entite_id=loan.id,
        details={
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "numero_dossier": loan.numero_dossier,
        },
    )
    from apps_coop.notifications.services import send_template

    send_template(
        "loan.disbursed",
        to=payment.member.user.email,
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "numero_dossier": loan.numero_dossier,
            "montant": _fmt_xaf(payment.montant),
            "date_premiere": loan.date_premiere_echeance.strftime("%d/%m/%Y"),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_not_implemented(payment: Payment, _raw: dict) -> None:
    raise NotImplementedError(
        f"Business hook for Payment.type={payment.type!r} is not implemented yet."
    )


_BUSINESS_HOOKS: dict[str, Callable[[Payment, dict], None]] = {
    Payment.Type.FRAIS_ADHESION: _hook_adhesion,
    Payment.Type.FRAIS_INSCRIPTION: _hook_adhesion,  # both activate the member
    Payment.Type.EPARGNE: _hook_savings_deposit,
    Payment.Type.EPARGNE_CLASSIQUE: _hook_classic_savings_deposit,
    Payment.Type.FRAIS_DEMANDE_CREDIT: _hook_loan_request_fees,
    Payment.Type.REMBOURSEMENT: _hook_loan_repayment,
    # FRAIS_RECONDUCTION : volontairement non mappé — la reconduction n'engendre
    # aucun frais (Règlement). Un paiement de ce type ne déclenche aucun hook.
    Payment.Type.FRAIS_CARNET: _hook_carnet_fees,
    Payment.Type.DECAISSEMENT: _hook_decaissement,
}
