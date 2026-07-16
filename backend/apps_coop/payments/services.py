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
) -> tuple[str | None, str, dict]:
    """Push a payin request to the configured provider.

    Returns ``(payment_url, provider_reference, provider_raw)``. La 3e
    valeur contient la reponse brute du provider (utile cote mobile pour
    afficher vendor / message Tara). Le Payment row est mis a jour en
    place avec ``reference_externe`` et ``gateway_initiated_at`` — le
    caller (view) doit le persister.
    """
    provider = get_provider(payment.provider_code or "tara")
    result = provider.init_payin(payment, phone=phone, network=network)
    payment.reference_externe = result.provider_reference
    payment.gateway_initiated_at = timezone.now()
    return result.payment_url, result.provider_reference, result.raw or {}


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
    # Match du Payment — 4 strategies en cascade. Tara ne renvoie PAS notre
    # productId dans le webhook (que collectionId numerique + phoneNumber +
    # paymentId), donc le matching par UUID ne marche qu'en theorie. En
    # pratique on tombe sur le fallback par phone + en_attente recent.
    raw_payload = raw_payload or {}
    payment = None
    match_strategy = None

    # Strategy 1 — UUID direct (rare en pratique, conserve pour compat)
    try:
        uuid.UUID(str(payment_idempotency_key))
        payment = Payment.objects.select_for_update().get(
            idempotency_key=payment_idempotency_key,
        )
        match_strategy = "uuid"
    except (ValueError, TypeError, Payment.DoesNotExist):
        payment = None

    # Strategy 2 — reference_externe == payment_idempotency_key ou provider_reference
    if payment is None:
        candidates = Payment.objects.select_for_update().filter(
            reference_externe=str(payment_idempotency_key),
        )
        if not candidates.exists() and provider_reference:
            candidates = Payment.objects.select_for_update().filter(
                reference_externe=str(provider_reference),
            )
        if candidates.exists():
            payment = candidates.filter(
                statut=Payment.Statut.EN_ATTENTE,
            ).order_by("-created_at").first() or candidates.order_by("-created_at").first()
            if payment is not None:
                match_strategy = "reference_externe"

    # Strategy 3 (NEW) — fallback par phoneNumber Tara : on cherche le Payment
    # EN_ATTENTE le plus recent (< 30 min) dont le membre a ce numero. Tara
    # envoie phoneNumber au format "237699XXXXXX" dans le webhook, donc on
    # compare apres normalisation. C'est notre seule chance quand Tara ne
    # renvoie ni productId UUID ni un ID qu'on a deja stocke en reference.
    if payment is None and raw_payload.get("phoneNumber"):
        from datetime import timedelta

        phone_raw = str(raw_payload["phoneNumber"])
        # Normalise les 2 sens : on accepte 2376XXX, +2376XXX, 6XXX, 06XXX.
        digits_only = "".join(c for c in phone_raw if c.isdigit())
        local_8_digits = digits_only[-9:] if len(digits_only) >= 9 else digits_only
        recent_cutoff = timezone.now() - timedelta(minutes=30)
        candidates = (
            Payment.objects.select_for_update()
            .filter(
                statut=Payment.Statut.EN_ATTENTE,
                created_at__gte=recent_cutoff,
                member__phone__icontains=local_8_digits,
            )
            .order_by("-created_at")
        )
        payment = candidates.first()
        if payment is not None:
            match_strategy = "phone_recent"

    if payment is None:
        logger.warning(
            "[TARA] webhook MATCH FAILED — key=%r ref=%r phone=%r status=%r — "
            "aucun Payment correspondant. Le membre a peut-etre debite son MoMo "
            "sans qu'on puisse rapprocher.",
            payment_idempotency_key,
            provider_reference,
            raw_payload.get("phoneNumber"),
            new_status,
        )
        raise Payment.DoesNotExist()

    logger.info(
        "[TARA] webhook MATCH OK — strategy=%s payment_id=%s status_now=%s -> %s",
        match_strategy,
        payment.id,
        payment.statut,
        new_status,
    )

    # On stocke le paymentId Tara comme reference_externe au passage, ca aidera
    # un eventuel rejeu webhook a matcher direct par strategy 2.
    if provider_reference and payment.reference_externe != provider_reference:
        payment.reference_externe = provider_reference
        payment.save(update_fields=["reference_externe", "updated_at"])

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

    _notify_payment_confirmed(payment)
    return payment


def _notify_payment_confirmed(payment: Payment) -> None:
    """Notif in-app systematique a la validation d'un Payment.

    Best-effort . n'echoue jamais. Couvre TOUS les types de paiement (epargne
    classique, cotisation, frais carnet, frais credit, remboursement,
    decaissement). Le membre voit ainsi son paiement passer de "en cours"
    a "valide" dans le centre de notifs mobile / portail, sans dependre du
    canal email.
    """
    if not payment.member_id or not getattr(payment.member, "user_id", None):
        return
    try:
        from apps_coop.notifications.services import create_notification

        type_display = payment.get_type_display() if hasattr(payment, "get_type_display") else payment.type
        create_notification(
            user=payment.member.user,
            type=f"payment.confirmed.{payment.type}",
            message=f"Paiement {type_display} de {_fmt_xaf(payment.montant)} FCFA valide.",
            lien="/notifications",
        )
    except Exception:  # noqa: BLE001
        logger.warning("payment.confirmed notification failed", exc_info=True)


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
    # Notif in-app — le membre doit voir le rejet dans son centre de notifs.
    if payment.member_id and getattr(payment.member, "user_id", None):
        try:
            from apps_coop.notifications.services import create_notification

            type_display = payment.get_type_display() if hasattr(payment, "get_type_display") else payment.type
            create_notification(
                user=payment.member.user,
                type=f"payment.rejected.{payment.type}",
                message=(
                    f"Paiement {type_display} de {_fmt_xaf(payment.montant)} FCFA echoue. "
                    f"{payment.motif_rejet[:120]}"
                ),
                lien="/notifications",
            )
        except Exception:  # noqa: BLE001 — best-effort
            logger.warning("payment.rejected notification failed", exc_info=True)
    return payment


def notify_payment_initiated(payment: Payment) -> None:
    """Cree une notif in-app "Paiement en cours" quand l'init Tara OK.

    Appele depuis la view ``init_payment`` apres le init_payin reussi. Le
    membre voit ainsi son paiement dans le centre de notifs meme s'il ne
    valide pas le STK Push (cas le plus frequent ou un Payment reste en
    en_attente perpetuellement).
    """
    if not payment.member_id or not getattr(payment.member, "user_id", None):
        return
    try:
        from apps_coop.notifications.services import create_notification

        type_display = payment.get_type_display() if hasattr(payment, "get_type_display") else payment.type
        create_notification(
            user=payment.member.user,
            type=f"payment.initiated.{payment.type}",
            message=(
                f"Paiement {type_display} de {_fmt_xaf(payment.montant)} FCFA en cours. "
                f"Valide le STK Push sur ton telephone."
            ),
            lien="/notifications",
        )
    except Exception:  # noqa: BLE001
        logger.warning("payment.initiated notification failed", exc_info=True)


# ---------------------------------------------------------------------------
# Business hooks per Payment.type
# ---------------------------------------------------------------------------
# Each hook receives the freshly-confirmed Payment and the raw provider
# payload. It must be idempotent and may NOT raise — log + record_audit on
# failure rather than blow up the webhook.


#: Les 3 frais d'adhésion exigés par le Règlement Intérieur (Art.3) — un
#: paiement validé de chacun de ces types est requis pour activer le Member.
_MEMBERSHIP_REQUIRED_FEES = (
    Payment.Type.FRAIS_ADHESION,
    Payment.Type.FRAIS_INSCRIPTION,
    Payment.Type.FRAIS_CARNET,
)


def _membership_fees_settled(member) -> bool:
    """True si les 3 frais d'adhésion (adhésion + inscription + carnet) ont
    chacun au moins un ``Payment`` validé pour ce membre.

    Lecture seule, idempotente, sans verrou — utilisée par les hooks qui
    décident d'activer ou non le Member.
    """
    paid_types = set(
        Payment.objects.filter(
            member=member,
            statut=Payment.Statut.VALIDE,
            type__in=_MEMBERSHIP_REQUIRED_FEES,
        ).values_list("type", flat=True)
    )
    return set(_MEMBERSHIP_REQUIRED_FEES).issubset(paid_types)


def _activate_member_if_fees_settled(member, *, trigger_payment: Payment) -> None:
    """CH-2 — bascule le Member à ``ACTIF`` UNIQUEMENT si les 3 frais sont
    payés. Sinon, log un audit ``membership.partial_payment`` et laisse le
    statut inchangé (typiquement ``SUSPENDU`` post-approbation).

    Idempotent : si le Member est déjà ``ACTIF``, no-op (cas du replay
    webhook ou du 4e paiement après activation). L'événement
    ``member.activated`` n'est émis qu'une seule fois — celui qui complète
    le triplet de frais.
    """
    from apps_coop.members.models import Member  # local import to avoid cycles

    if member.statut == Member.Statut.ACTIF:
        return

    if not _membership_fees_settled(member):
        record_audit(
            action="membership.partial_payment",
            entite_type="Member",
            entite_id=member.id,
            details={
                "trigger_payment_id": trigger_payment.id,
                "trigger_type": trigger_payment.type,
                "montant": str(trigger_payment.montant),
            },
        )
        return

    member.statut = Member.Statut.ACTIF
    member.save(update_fields=["statut", "updated_at"])
    record_audit(
        action="member.activated",
        entite_type="Member",
        entite_id=member.id,
        details={
            "trigger": "membership_fees_complete",
            "completing_payment_id": trigger_payment.id,
            "completing_type": trigger_payment.type,
        },
    )
    from apps_coop.notifications.events import emit_event

    emit_event(
        "member.activated",
        member=member,
        context={
            "prenom": member.prenom,
            "numero_membre": member.numero_membre,
            "montant": _fmt_xaf(trigger_payment.montant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_adhesion(payment: Payment, _raw: dict) -> None:
    """UC1 — frais d'adhésion ou d'inscription reçu.

    Depuis CH-2 (chantier juin 2026), le Member ne bascule à ``ACTIF`` QUE
    lorsque les 3 frais (adhésion + inscription + carnet, 13 000 FCFA cumulés
    par défaut) sont tous payés. Le paiement isolé d'un seul frais laisse le
    Member ``SUSPENDU`` — voir ``_activate_member_if_fees_settled``.
    """
    _activate_member_if_fees_settled(payment.member, trigger_payment=payment)


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
    # get_or_create défensif (aligné sur l'épargne classique) : un membre sans
    # compte collecte (ex. bénéficiaire campagne créé sans dépôt) ne doit PAS
    # faire échouer la validation du paiement (sinon Payment bloqué en_attente
    # et solde à 0 malgré un versement encaissé).
    SavingsAccount.objects.get_or_create(member=payment.member)
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

    # L7 — impute l'écriture au carnet le plus récent du membre (le cas échéant).
    from apps_coop.members.models import BookletOrder

    transaction_row = SavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=SavingsTransaction.TypeOp.DEPOT,
        montant=payment.montant,
        solde_apres=nouveau_solde,
        date=valued_at,
        # LOT 6 (refonte 2026) — propage le multi-jours pré-payé.
        nb_jours_couverts=payment.nb_jours_couverts,
        booklet_order=BookletOrder.latest_for(payment.member),
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
    from apps_coop.notifications.events import emit_event

    emit_event(
        "savings.deposit_confirmed",
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

    CH-3 — Sous-canal **placement** : si ``payment.is_placement`` est True, le
    dépôt alimente aussi automatiquement la convention prêteur (LOT 7) :
      • Auto-création du ``LenderConsent`` (Mode B / tranches) si le membre
        n'en a pas encore — convention signée implicitement à la date du dépôt.
      • Création d'une ``LenderTranche`` DISPONIBLE du même montant que le
        dépôt. L'admin pourra ensuite l'engager dans un crédit (LOT 8 funding).
    Le partage des intérêts crédit ainsi générés reste piloté par
    ``lender.interest_share_rate`` (LOT 9) — éditable depuis Paramètres admin.
    """
    from apps_coop.audit.services import get_str_setting
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        LenderConsent,
        LenderTranche,
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

    date_op = payment.date_validation or timezone.now()

    # L7 — impute l'écriture au carnet le plus récent du membre (le cas échéant).
    from apps_coop.members.models import BookletOrder

    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=payment,
        type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        montant=payment.montant,
        solde_apres=nouveau_solde,
        date=date_op,
        is_placement=payment.is_placement,
        booklet_order=BookletOrder.latest_for(payment.member),
        # `placement_unlock_date` reste null : le verrou vient de l'état de la
        # tranche prêteur (DISPONIBLE/ENGAGEE), pas d'une date fixe.
    )

    # Placement fermé (toggle off, après la date-limite globale, OU membre
    # hors de sa fenêtre des N premiers mois d'ancienneté) → le versement reste
    # en épargne LIBRE : aucune tranche créée.
    from apps_coop.savings.placement import placement_open_for_member

    tranche_id: int | None = None
    if payment.is_placement and placement_open_for_member(payment.member):
        consent, _ = LenderConsent.objects.get_or_create(
            member=payment.member,
            defaults={
                "is_global": False,
                "convention_signed_at": date_op,
            },
        )
        # On crée la tranche même si le consentement a été révoqué — le membre
        # vient de placer explicitement, c'est un signe de réactivation.
        if consent.revoked_at is not None:
            consent.revoked_at = None
            consent.revoked_by = None
            consent.save(update_fields=["revoked_at", "revoked_by", "updated_at"])

        tranche = LenderTranche.objects.create(
            member=payment.member,
            montant=payment.montant,
            statut=LenderTranche.Statut.DISPONIBLE,
        )
        tranche_id = tranche.id

    record_audit(
        action="classic_savings.deposit",
        entite_type="ClassicSavingsAccount",
        entite_id=account.id,
        details={
            "member_id": payment.member_id,
            "payment_id": payment.id,
            "montant": str(payment.montant),
            "solde_apres": str(nouveau_solde),
            "is_placement": payment.is_placement,
            "lender_tranche_id": tranche_id,
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

    # LOT 9 — import paresseux pour éviter le cycle loans <-> payments.
    from apps_coop.loans.lender_payouts import (
        distribute_interest_share,
        release_loan_tranches,
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
        # LOT 9 — Partage 50/50 des intérêts (no-op si crédit legacy sans
        # LenderAllocation, ou si la portion intérêt de l'imputation = 0).
        distribute_interest_share(
            installment=inst,
            payment=payment,
            imputation=impute,
        )
        impacted.append({"installment": inst.numero_echeance, "impute": str(impute), "statut": inst.statut})
        reste -= impute

    impute_total = Decimal(payment.montant) - reste
    loan.solde_restant = max(Decimal(loan.solde_restant) - impute_total, Decimal("0"))

    all_installments = LoanInstallment.objects.filter(loan=loan)
    all_paid = not all_installments.exclude(statut=LoanInstallment.Statut.PAYEE).exists()
    any_late = all_installments.filter(statut=LoanInstallment.Statut.EN_RETARD).exists()

    just_closed = False
    if all_paid:
        if loan.statut != Loan.Statut.CLOTURE:
            just_closed = True
        loan.statut = Loan.Statut.CLOTURE
    elif loan.statut == Loan.Statut.EN_RETARD and not any_late:
        loan.statut = Loan.Statut.ACTIF

    loan.save(update_fields=["solde_restant", "statut", "updated_at"])

    # LOT 9 — À la clôture intégrale, on libère les tranches engagées par les
    # prêteurs (DISPONIBLE → ENGAGEE → LIBEREE). Idempotent : un déclenchement
    # multiple par replay du webhook ne re-marque pas les tranches.
    if just_closed:
        release_loan_tranches(loan)

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
    from apps_coop.notifications.events import emit_event

    emit_event(
        "loan.repayment_confirmed",
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

    candidates_qs = LoanRequest.objects.select_for_update().filter(
        member=payment.member, statut=LoanRequest.Statut.EN_ATTENTE,
    )
    candidates_count = candidates_qs.count()
    pending = candidates_qs.order_by("-date_soumission").first()

    # O3 . log si plus d'une demande EN_ATTENTE (ne devrait JAMAIS arriver
    # grace a compute_eligibility, mais detection de bug eventuel).
    if candidates_count > 1:
        logger.warning(
            "Payment #%s . %s LoanRequest EN_ATTENTE trouvees pour le membre "
            "%s (attendu: 1). Mappage applique sur la plus recente #%s. "
            "Investigation requise sur compute_eligibility.",
            payment.id, candidates_count, payment.member_id,
            pending.id if pending else None,
        )
    if pending is None:
        logger.warning(
            "Payment #%s (frais_demande_credit) validé mais aucune LoanRequest "
            "en_attente trouvée pour le membre %s — webhook orphelin ?",
            payment.id,
            payment.member_id,
        )
        return

    # Point unique du parcours post-frais : ouvre l'instruction, ou sollicite
    # l'avaliste désigné à la soumission (« frais d'abord, avaliste ensuite »).
    from apps_coop.loans.study_fee_services import open_instruction_after_fees

    open_instruction_after_fees(pending)
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
    from apps_coop.notifications.events import emit_event

    emit_event(
        "loan_request.fees_paid",
        member=payment.member,
        context={
            "prenom": payment.member.prenom,
            "request_id": pending.id,
            "montant": _fmt_xaf(payment.montant),
            "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
        },
    )


def _hook_carnet_fees(payment: Payment, raw: dict) -> None:
    """Frais de carnet réglés . trois flows distincts selon le contexte :

      1. 1ere adhesion (membre SUSPENDU, pas encore les 3 frais soldes)
         -> Cree BookletOrder + tentative activation CH-2 (legacy)
      2. Renouvellement annuel (membre ACTIF/SUSPENDU dans la fenetre
         d'anniversaire, ou flag is_renewal dans raw)
         -> Pose date_derniere_reinscription = today, reactive si SUSPENDU
            pour cause de non-renouvellement, PAS de nouveau BookletOrder
            cree par defaut (le carnet en cours reste utilise ; un nouveau
            est imprime via les admin tools si besoin).
      3. Commande carnet supplementaire (carnet perdu hors fenetre)
         -> Cree BookletOrder. Pas de renouvellement.

    Idempotent dans les 3 cas.
    """
    from apps_coop.members.models import BookletOrder

    is_renewal = _is_carnet_renewal(payment, raw)

    # L7 (réforme 2026) — Découplage carnet ↔ renouvellement : la ré-inscription
    # annuelle est appliquée si applicable, MAIS un nouveau carnet est TOUJOURS
    # créé (décision « chaque commande = nouveau carnet »). Plusieurs carnets
    # par an sont donc possibles ; les écritures s'imputent au plus récent.
    if is_renewal:
        _apply_membership_renewal(payment)

    order, created = BookletOrder.objects.get_or_create(
        payment=payment,
        defaults={
            "member": payment.member,
            "statut": BookletOrder.Statut.PAYEE,
            "annee": timezone.localdate().year,
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
    if created:
        from apps_coop.notifications.events import emit_event

        emit_event(
            "booklet.ordered",
            member=payment.member,
            context={
                "prenom": payment.member.prenom,
                "numero_membre": payment.member.numero_membre,
                "montant": _fmt_xaf(payment.montant),
                "portal_url": getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
            },
        )

    # CH-2 — tentative d'activation : si c'est le 3e frais qui complète
    # le triplet (adhésion + inscription + carnet), le Member passe à ACTIF.
    # Idempotent : si déjà actif (4e+ paiement), no-op. Inutile en
    # renouvellement (le membre a déjà été actif au moins une fois).
    if not is_renewal:
        _activate_member_if_fees_settled(payment.member, trigger_payment=payment)


# ---------------------------------------------------------------------------
# D1 . Renouvellement annuel d'adhesion (chantier 2026-06)
# ---------------------------------------------------------------------------
#
# Le membre paie 1 fois par an son carnet pour renouveler son adhesion. Le
# compte (numero_membre, solde epargne, historique) reste IDENTIQUE . seule
# Member.date_derniere_reinscription est mise a jour, ce qui decale la
# prochaine echeance de 12 mois.
#
# Suspension auto J+30 grace : voir cron rappel_reinscription_annuelle (D2).
# Reactivation : si Member.statut == SUSPENDU au moment du paiement carnet
# de renouvellement, on rebascule ACTIF.

def _is_carnet_renewal(payment: Payment, raw: dict) -> bool:
    """Vrai si le paiement frais_carnet est un renouvellement annuel.

    Critere : flag `is_renewal` dans raw (cash-in admin explicite), OU
    Member statut ACTIF/SUSPENDU et dans la fenetre d'anniversaire (a
    partir de J-60 avant `prochaine_reinscription_due`).

    Faux pour : 1ere adhesion (TEMPORAIRE ou SUSPENDU sans frais soldes),
    commande de carnet supplementaire hors fenetre (carnet perdu).
    """
    from datetime import timedelta
    from apps_coop.members.models import Member

    # Flag explicite pose par cash-in admin (D6) ou init_payment via flag.
    if raw and raw.get("is_renewal") is True:
        return True

    member = payment.member
    if member is None:
        return False
    if member.statut not in (Member.Statut.ACTIF, Member.Statut.SUSPENDU):
        return False
    # Pour qu'un renouvellement ait du sens, le membre doit avoir deja
    # solde ses 3 frais d'adhesion une fois.
    if not _membership_fees_settled(member):
        return False
    # Fenetre d'anniversaire : a partir de J-60 jusqu'a tres tard
    # (couvre la grace J+30 et au-dela pour reactivation suspension).
    base = member.date_derniere_reinscription
    if base is None:
        return False
    today = timezone.localdate()
    fenetre_debut = base + timedelta(days=305)  # J-60 avant J+365
    return today >= fenetre_debut


def _apply_membership_renewal(payment: Payment) -> None:
    """Applique le renouvellement annuel : pose date_derniere_reinscription
    et reactive si Member etait SUSPENDU pour non-renouvellement.

    Idempotent. Pas de creation BookletOrder par defaut (le carnet
    courant reste valide). Pas de nouvelle activation CH-2 (le membre
    a deja ete actif au moins une fois).
    """
    from apps_coop.members.models import Member
    from apps_coop.members.services import confirm_member_reinscription

    member = payment.member
    was_suspended = member.statut == Member.Statut.SUSPENDU

    confirm_member_reinscription(
        member,
        confirmed_by=getattr(payment, "validated_by", None),
        paid_amount=payment.montant,
        note=f"Auto via paiement #{payment.id} ({payment.source})",
    )

    if was_suspended:
        # Reactivation : on suppose que la suspension etait pour
        # non-renouvellement (le cron D2 enregistre la raison dans audit).
        member.statut = Member.Statut.ACTIF
        member.save(update_fields=["statut", "updated_at"])
        record_audit(
            action="member.reactivated_via_renewal",
            entite_type="Member",
            entite_id=member.id,
            details={
                "payment_id": payment.id,
                "trigger": "carnet_fees_renewal",
            },
        )


def _hook_decaissement(payment: Payment, _raw: dict) -> None:
    """Décaissement validé (payout Tara confirmé). Deux origines possibles :

      1. **Crédit** → ``payment.loan_id`` rempli (cf. ``disburse_loan_via_tara``).
         Met le Loan en ``actif`` + ``date_decaissement = aujourd'hui``.
      2. **Retrait épargne** → reverse ``WithdrawalRequest`` via le OneToOne
         (cf. ``savings.services._init_payout_for_withdrawal``). Marque la WR
         en ``COMPLETEE`` + notifie le membre.

    L'idempotence contre les rejeux est assurée par ``handle_webhook_event``
    (le même Payment ne déclenche pas 2× le hook).
    """
    from apps_coop.loans.models import Loan
    from apps_coop.savings.models import WithdrawalRequest

    # Cas 2 : payout de retrait d'épargne.
    wr = getattr(payment, "withdrawal_request", None)
    if wr is not None:
        wr.statut = WithdrawalRequest.Statut.COMPLETEE
        wr.save(update_fields=["statut", "updated_at"])
        record_audit(
            action="withdrawal.payout_completed",
            entite_type="WithdrawalRequest",
            entite_id=wr.id,
            details={
                "payment_id": payment.id,
                "montant": str(payment.montant),
                "reference_externe": payment.reference_externe,
            },
        )
        # Notif membre — best-effort, ne doit pas casser le webhook.
        try:
            from apps_coop.notifications.events import emit_event

            emit_event(
                "withdrawal.completed",
                member=payment.member,
                context={
                    "prenom": payment.member.prenom,
                    "montant": _fmt_xaf(payment.montant),
                    "mode_paiement": wr.get_mode_paiement_display(),
                    "portal_url": getattr(
                        settings, "FRONTEND_BASE_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("withdrawal.completed notification skipped", exc_info=True)
        return

    if payment.loan_id is None:
        logger.error(
            "Payment #%s (decaissement) sans loan_id ni withdrawal_request — orphelin.",
            payment.id,
        )
        return

    loan = Loan.objects.select_for_update().get(pk=payment.loan_id)
    loan.date_decaissement = timezone.localdate()
    loan.statut = Loan.Statut.ACTIF
    loan.save(update_fields=["date_decaissement", "statut", "updated_at"])

    # CH-12 — Si mode source + prêteurs, distribue immédiatement leur part
    # 50 % des intérêts retenus. Idempotent : ne s'exécute qu'une fois par
    # crédit même en cas de rejeu du webhook.
    try:
        from apps_coop.loans.lender_payouts import (
            distribute_interest_share_at_source,
        )

        distribute_interest_share_at_source(loan, payment)
    except Exception:  # noqa: BLE001 — best-effort, ne casse pas le hook.
        logger.warning(
            "distribute_interest_share_at_source a échoué pour Loan=%s",
            loan.id, exc_info=True,
        )

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
    from apps_coop.notifications.events import emit_event

    emit_event(
        "loan.disbursed",
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
