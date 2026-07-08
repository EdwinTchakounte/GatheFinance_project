"""Service-layer functions for the savings withdrawal flow.

Politique (cf. WithdrawalRequest) : le membre demande un retrait, l'admin
valide. À l'approbation, le solde est débité via une SavingsTransaction
`retrait`. Atomique + idempotent.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    get_str_setting,
    record as record_audit,
)

from .models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
    WithdrawalRequest,
)


logger = logging.getLogger(__name__)


def _add_months(d: date, months: int) -> date:
    """Avance une ``date`` de N mois (clamp au dernier jour du mois cible)."""
    total_months = (d.year * 12 + d.month - 1) + months
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    last_day = monthrange(new_year, new_month)[1]
    return d.replace(year=new_year, month=new_month, day=min(d.day, last_day))


def classic_withdrawable(account: ClassicSavingsAccount) -> Decimal:
    """Part réellement retirable de l'épargne classique (réforme garantie 2026).

    = solde − max(placement encore actif, gel de garantie crédit).

    Le placement est déjà bloqué (sous-canal CH-3). Le gel de garantie (caution
    engagée comme avaliste + collatéral immobilisé comme demandeur) « grise »
    en plus la part libre — mais uniquement au-delà du placement, puisque le
    placement compte déjà dans la garantie et est déjà indisponible.
    """
    solde = Decimal(account.solde)
    placement = Decimal(account.solde_placement_actif)
    frozen = Decimal("0")
    try:  # import local — évite un cycle savings <-> loans au chargement.
        from apps_coop.loans.avaliste_services import member_frozen_guarantee

        frozen = member_frozen_guarantee(account.member)
    except Exception:  # noqa: BLE001 — best-effort, ne bloque jamais un retrait
        logger.warning(
            "member_frozen_guarantee a échoué pour le compte classique #%s",
            account.pk,
        )
    dispo = solde - max(placement, frozen)
    return dispo if dispo > 0 else Decimal("0")


@transaction.atomic
def request_withdrawal(
    account: SavingsAccount | None = None,
    *,
    montant: Decimal,
    motif: str = "",
    mode_paiement: str = WithdrawalRequest.ModePaiement.PRESENTIEL,
    recipient_phone: str = "",
    network: str = "",
    source: str = WithdrawalRequest.Source.COLLECTE,
    classic_account: ClassicSavingsAccount | None = None,
) -> WithdrawalRequest:
    """Crée une `WithdrawalRequest(en_attente)`.

    Le membre choisit son **produit source** (``source``) :
      • ``COLLECTE`` — retrait sur le compte de collecte journalière
        (``account`` requis). Solde disponible = ``account.solde``.
      • ``CLASSIQUE_LIBRE`` — retrait sur la **part libre** de l'épargne
        classique (``classic_account`` requis). Solde disponible =
        ``classic_account.solde_libre`` (= solde total − placements encore
        actifs). Le placement reste bloqué : un retrait classique ne peut
        jamais l'entamer.

    Puis son **canal de remise** (``mode_paiement``) :
      • ``MOMO`` — il fournit ``recipient_phone`` + ``network``.
      • ``PRESENTIEL`` — argent à retirer à l'agence.

    Règles :
      - montant strictement positif
      - montant ≤ solde disponible du produit source (verrou ligne pour éviter
        une demande au-dessus du solde en cas de mouvements concurrents)
      - pas de demande déjà `en_attente` pour ce produit (un retrait à la fois)
      - mode MOMO ⇒ phone + réseau renseignés (réseau dans la whitelist)
    """
    montant = Decimal(montant)
    if montant <= 0:
        raise ValueError("Le montant du retrait doit être positif.")

    mode = (mode_paiement or WithdrawalRequest.ModePaiement.PRESENTIEL).strip()
    if mode not in WithdrawalRequest.ModePaiement.values:
        raise ValueError(f"Mode de paiement invalide : {mode!r}.")

    recipient_phone = (recipient_phone or "").strip()
    network = (network or "").strip().upper()

    if mode == WithdrawalRequest.ModePaiement.MOMO:
        if not recipient_phone:
            raise ValueError("Le numéro Mobile Money est requis pour un retrait MOMO.")
        if network not in WithdrawalRequest.Network.values:
            raise ValueError(
                f"Réseau Mobile Money invalide : {network!r}. "
                f"Choisis parmi {sorted(WithdrawalRequest.Network.values)}."
            )
    else:
        # En présentiel on ignore phone+network (mais on les vide pour rester clean)
        recipient_phone = ""
        network = ""

    source = source or WithdrawalRequest.Source.COLLECTE
    if source == WithdrawalRequest.Source.CLASSIQUE_LIBRE:
        if classic_account is None:
            raise ValueError("Compte épargne classique requis pour un retrait classique.")
        locked = ClassicSavingsAccount.objects.select_for_update().get(pk=classic_account.pk)
        # Part retirable = solde − max(placement actif, gel garantie crédit).
        disponible = classic_withdrawable(locked)
        account_kwargs = {"classic_account": locked}
        pending_filter = {"classic_account": locked}
    else:
        if account is None:
            raise ValueError("Compte de collecte requis pour un retrait collecte.")
        locked = SavingsAccount.objects.select_for_update().get(pk=account.pk)
        disponible = Decimal(locked.solde)
        account_kwargs = {"account": locked}
        pending_filter = {"account": locked}

    if montant > disponible:
        raise ValueError(
            f"Montant demandé ({montant}) supérieur au solde disponible "
            f"({disponible})."
        )

    existing = (
        WithdrawalRequest.objects.select_for_update()
        .filter(statut=WithdrawalRequest.Statut.EN_ATTENTE, **pending_filter)
        .first()
    )
    if existing:
        raise ValueError(
            "Une demande de retrait est déjà en attente. Attends la décision "
            "de l'administration avant d'en soumettre une nouvelle."
        )

    member = locked.member
    wr = WithdrawalRequest.objects.create(
        montant=montant,
        motif=(motif or "").strip(),
        mode_paiement=mode,
        recipient_phone=recipient_phone,
        network=network,
        source=source,
        **account_kwargs,
    )
    record_audit(
        action="withdrawal.requested",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=member.user,
        details={
            "member_id": member.id,
            "montant": str(montant),
            "solde": str(disponible),
            "source": source,
        },
    )

    # Accusé de réception au membre (best-effort — ne casse jamais le flow).
    if getattr(member.user, "email", None):
        try:
            from django.conf import settings as dj_settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "withdrawal.requested",
                member=member,
                context={
                    "prenom": member.prenom,
                    "montant": f"{int(montant):,}".replace(",", " "),
                    "portal_url": getattr(
                        dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("withdrawal.requested email skipped", exc_info=True)
    return wr


def decide_withdrawal(
    wr: WithdrawalRequest,
    *,
    decided_by,
    approve: bool,
    motif_rejet: str = "",
) -> WithdrawalRequest:
    """Approuve ou rejette une demande de retrait.

    Idempotent : si déjà décidée, renvoie la demande telle quelle.

    À l'**approbation** :
      1. Revérifie le solde sous verrou + débit + ``SavingsTransaction(retrait)``.
      2. Si ``mode_paiement = PRESENTIEL`` → statut ``APPROUVEE`` (l'admin
         cliquera ensuite « Confirmer remise espèces » via ``mark_withdrawal_paid``
         qui passera à ``COMPLETEE``).
      3. Si ``mode_paiement = MOMO`` → on crée un ``Payment(decaissement,
         mobile_money, en_attente)`` lié à la WR, on appelle
         ``provider.init_payout()``, statut ``EN_PAYOUT``. Le webhook Tara
         basculera vers ``COMPLETEE`` via ``_hook_decaissement``.

    **Note transaction** : volontairement pas ``@transaction.atomic`` global —
    l'appel HTTP Tara doit pouvoir laisser une trace ``payout_failed`` même si
    l'init payout lève une exception (sinon rollback complet du débit).
    """
    if wr.statut != WithdrawalRequest.Statut.EN_ATTENTE:
        return wr  # déjà traitée — idempotent

    now = timezone.now()

    if not approve:
        with transaction.atomic():
            motif_rejet = (motif_rejet or "").strip()
            if not motif_rejet:
                raise ValueError("Un motif de rejet est requis.")
            wr.statut = WithdrawalRequest.Statut.REJETEE
            wr.motif_rejet = motif_rejet
            wr.decide_par = decided_by
            wr.date_decision = now
            wr.save(
                update_fields=[
                    "statut", "motif_rejet", "decide_par", "date_decision", "updated_at",
                ]
            )
        record_audit(
            action="withdrawal.rejected",
            entite_type="WithdrawalRequest",
            entite_id=wr.id,
            user=decided_by,
            details={"motif": motif_rejet},
        )
        _notify(wr, approved=False)
        return wr

    # --- Approbation : débit du solde, sous verrou (atomique court) ---
    montant = Decimal(wr.montant)
    with transaction.atomic():
        if wr.source == WithdrawalRequest.Source.CLASSIQUE_LIBRE:
            # Débit sur l'épargne classique — jamais au-delà de la part libre
            # (le placement encore actif garantit les engagements crédit).
            cacc = ClassicSavingsAccount.objects.select_for_update().get(
                pk=wr.classic_account_id
            )
            disponible = classic_withdrawable(cacc)
            if montant > disponible:
                raise ValueError(
                    f"Solde retirable insuffisant pour approuver : {disponible} "
                    f"< {montant} (placement bloqué + gel garantie crédit)."
                )
            nouveau_solde = Decimal(cacc.solde) - montant
            cacc.solde = nouveau_solde
            cacc.save(update_fields=["solde", "updated_at"])

            ctx = ClassicSavingsTransaction.objects.create(
                account=cacc,
                payment=None,  # mouvement interne, pas un Payment entrant
                type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
                montant=montant,
                solde_apres=nouveau_solde,
                date=now,
            )
            wr.classic_transaction = ctx
            tx_field, tx_id = "classic_transaction", ctx.id
        else:
            account = SavingsAccount.objects.select_for_update().get(pk=wr.account_id)
            if montant > Decimal(account.solde):
                raise ValueError(
                    f"Solde insuffisant pour approuver : {account.solde} < {montant}."
                )
            nouveau_solde = Decimal(account.solde) - montant
            account.solde = nouveau_solde
            account.save(update_fields=["solde", "updated_at"])

            tx = SavingsTransaction.objects.create(
                account=account,
                payment=None,  # mouvement interne, pas un Payment entrant
                type_op=SavingsTransaction.TypeOp.RETRAIT,
                montant=montant,
                solde_apres=nouveau_solde,
                date=now,
            )
            wr.transaction = tx
            tx_field, tx_id = "transaction", tx.id

        wr.decide_par = decided_by
        wr.date_decision = now
        if wr.mode_paiement == WithdrawalRequest.ModePaiement.PRESENTIEL:
            wr.statut = WithdrawalRequest.Statut.APPROUVEE
            wr.save(
                update_fields=[
                    "statut", tx_field, "decide_par", "date_decision", "updated_at",
                ]
            )
        else:
            # MOMO : statut intermédiaire — on bascule en EN_PAYOUT après init Tara
            wr.statut = WithdrawalRequest.Statut.EN_ATTENTE  # provisoire, sera écrasé
            wr.save(
                update_fields=[
                    tx_field, "decide_par", "date_decision", "updated_at",
                ]
            )

    record_audit(
        action="withdrawal.approved",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=decided_by,
        details={
            "montant": str(montant),
            "solde_apres": str(nouveau_solde),
            "transaction_id": tx_id,
            "source": wr.source,
            "mode_paiement": wr.mode_paiement,
        },
    )

    # --- MOMO : init payout Tara hors transaction ---
    if wr.mode_paiement == WithdrawalRequest.ModePaiement.MOMO:
        _init_payout_for_withdrawal(wr, decided_by=decided_by)
        wr.refresh_from_db()

    _notify(wr, approved=True)
    return wr


def _init_payout_for_withdrawal(wr: WithdrawalRequest, *, decided_by) -> None:
    """Crée un Payment(decaissement, en_attente) + appelle Tara init_payout.

    En cas de succès : Payment garde son `reference_externe`, WR passe en
    ``EN_PAYOUT``. Le webhook Tara confirmera et basculera en ``COMPLETEE``
    via ``_hook_decaissement``.

    En cas d'échec Tara : Payment est marqué ``rejete`` (avec motif), WR
    passe en ``PAYOUT_FAILED``. L'admin pourra réessayer via
    ``retry_withdrawal_payout``.
    """
    import uuid

    from apps_coop.payments.models import Payment
    from apps_coop.payments.providers import get_provider
    from apps_coop.payments.providers.base import ProviderError

    # 1) Crée le Payment décaissement (atomique court)
    with transaction.atomic():
        payment = Payment.objects.create(
            member=wr.member,
            montant=wr.montant,
            type=Payment.Type.DECAISSEMENT,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code="tara",
            validated_by=decided_by,
            date_versement=timezone.now(),
            loan=None,
            idempotency_key=uuid.uuid4(),
        )
        wr.payout_payment = payment
        wr.save(update_fields=["payout_payment", "updated_at"])

    # 2) Appel provider hors transaction
    provider = get_provider("tara")
    try:
        result = provider.init_payout(
            payment,
            recipient_phone=wr.recipient_phone,
            network=wr.network,
        )
    except ProviderError as exc:
        payment.statut = Payment.Statut.REJETE
        payment.motif_rejet = str(exc)[:500]
        payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
        wr.statut = WithdrawalRequest.Statut.PAYOUT_FAILED
        wr.motif_rejet = f"Payout Tara : {exc}"[:2000]
        wr.save(update_fields=["statut", "motif_rejet", "updated_at"])
        record_audit(
            action="withdrawal.payout_failed",
            entite_type="WithdrawalRequest",
            entite_id=wr.id,
            user=decided_by,
            details={
                "payment_id": payment.id,
                "reason": str(exc),
                "retryable": exc.retryable,
            },
        )
        return

    payment.reference_externe = result.provider_reference or ""
    payment.gateway_initiated_at = timezone.now()
    payment.save(
        update_fields=["reference_externe", "gateway_initiated_at", "updated_at"]
    )
    wr.statut = WithdrawalRequest.Statut.EN_PAYOUT
    wr.save(update_fields=["statut", "updated_at"])

    record_audit(
        action="withdrawal.payout_initiated",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=decided_by,
        details={
            "payment_id": payment.id,
            "reference_externe": payment.reference_externe,
            "recipient_phone_masked": (
                wr.recipient_phone[:4] + "***" + wr.recipient_phone[-2:]
                if len(wr.recipient_phone) >= 6
                else "***"
            ),
            "network": wr.network,
        },
    )

    # Mode recette flows complets — auto-validate (cf. settings.PAYMENTS_TEST_AUTO_VALIDATE).
    # Joue le webhook DECAISSEMENT "valide" immédiatement, le hook
    # `_hook_decaissement` basculera la WR en COMPLETEE.
    from django.conf import settings as dj_settings

    if getattr(dj_settings, "PAYMENTS_TEST_AUTO_VALIDATE", False):
        from apps_coop.payments.services import handle_webhook_event

        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference=payment.reference_externe,
            raw_payload={"auto_validate": True, "mode": "test", "kind": "payout"},
        )


@transaction.atomic
def mark_withdrawal_paid(
    wr: WithdrawalRequest,
    *,
    agent,
    note: str = "",
) -> WithdrawalRequest:
    """Marque un retrait **présentiel** comme remis (espèces données au membre).

    Précondition : statut == ``APPROUVEE`` (le solde est déjà débité). Idempotent :
    si déjà ``COMPLETEE``, renvoie tel quel. Une remise espèces ne s'applique
    qu'aux retraits ``mode_paiement = PRESENTIEL`` (MOMO passe par le webhook).
    """
    if wr.statut == WithdrawalRequest.Statut.COMPLETEE:
        return wr  # idempotent

    if wr.mode_paiement != WithdrawalRequest.ModePaiement.PRESENTIEL:
        raise ValueError(
            "Le marquage espèces ne s'applique qu'aux retraits en présentiel."
        )
    if wr.statut != WithdrawalRequest.Statut.APPROUVEE:
        raise ValueError(
            f"Statut {wr.statut!r} — seul un retrait approuvé peut être marqué remis."
        )

    now = timezone.now()
    wr.statut = WithdrawalRequest.Statut.COMPLETEE
    wr.handed_over_by = agent
    wr.handed_over_at = now
    wr.save(update_fields=["statut", "handed_over_by", "handed_over_at", "updated_at"])

    record_audit(
        action="withdrawal.handed_over",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=agent,
        details={"note": note[:200]},
    )

    _notify(wr, approved=True, completed=True)
    return wr


@transaction.atomic
def retry_withdrawal_payout(
    wr: WithdrawalRequest,
    *,
    agent,
) -> WithdrawalRequest:
    """Réessaie un payout MOMO en ``PAYOUT_FAILED``.

    Repart de zéro côté Tara (nouveau Payment + nouvel ``idempotency_key``),
    mais réutilise la même ``WithdrawalRequest`` (le solde est déjà débité).
    """
    if wr.mode_paiement != WithdrawalRequest.ModePaiement.MOMO:
        raise ValueError("Réessai applicable uniquement aux retraits MOMO.")
    if wr.statut != WithdrawalRequest.Statut.PAYOUT_FAILED:
        raise ValueError(
            f"Statut {wr.statut!r} — seul un PAYOUT_FAILED peut être réessayé."
        )

    # Repasse provisoirement à EN_ATTENTE puis init_payout posera le bon statut
    wr.statut = WithdrawalRequest.Statut.EN_ATTENTE
    wr.motif_rejet = ""
    wr.payout_payment = None
    wr.save(update_fields=["statut", "motif_rejet", "payout_payment", "updated_at"])

    _init_payout_for_withdrawal(wr, decided_by=agent)
    wr.refresh_from_db()
    return wr


def _notify(wr: WithdrawalRequest, *, approved: bool, completed: bool = False) -> None:
    """Email + notif in-app au membre (best-effort, ne casse jamais le flow).

    Trois templates possibles :
      • ``withdrawal.rejected`` — décision négative
      • ``withdrawal.approved`` — décision positive (mode présentiel : argent
        disponible à l'agence ; mode MOMO : payout en cours)
      • ``withdrawal.completed`` — argent effectivement remis (espèces
        marquées par l'admin OU payout Tara confirmé par le webhook)
    """
    from django.conf import settings as dj_settings

    from apps_coop.notifications.events import emit_event

    member = wr.member
    if not getattr(member.user, "email", None):
        return
    if completed:
        code = "withdrawal.completed"
    else:
        code = "withdrawal.approved" if approved else "withdrawal.rejected"
    try:
        emit_event(
            code,
            member=member,
            context={
                "prenom": member.prenom,
                "montant": f"{int(wr.montant):,}".replace(",", " "),
                "motif_rejet": wr.motif_rejet,
                "mode_paiement": wr.get_mode_paiement_display(),
                "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("withdrawal notification failed for %s", code, exc_info=True)


# ===========================================================================
# LOT 5 (refonte 2026) — Épargne classique : anniversaire 1 an + renouvellement
# ===========================================================================


@transaction.atomic
def renew_classic_savings_account(
    *,
    account: ClassicSavingsAccount,
    paid_by=None,
    paid_amount: Decimal | None = None,
) -> ClassicSavingsAccount:
    """Acte le renouvellement annuel d'un compte d'épargne classique.

    Précondition : ``statut_renouvellement != ARCHIVE`` (un compte archivé
    n'est plus renouvelable — il faut en ouvrir un nouveau).

    Effets atomiques :
      - Écrit ``ClassicSavingsTransaction(FRAIS_RENOUVELLEMENT, montant=renewal_fee)``
      - ``cycle_courant += 1``
      - ``date_prochaine_maturite = today + epargne.contract_months``
      - ``statut_renouvellement = ACTIF``
      - Audit + event ``savings.renewed``

    Le ``paid_amount`` est informatif (la transaction du paiement vit dans
    le module Payments). Si fourni, on l'écrit dans l'audit pour piste.
    """
    locked = ClassicSavingsAccount.objects.select_for_update().get(pk=account.pk)
    if locked.statut_renouvellement == ClassicSavingsAccount.StatutRenouvellement.ARCHIVE:
        raise ValueError(
            "Compte archivé — renouvellement impossible, ouvrir un nouveau compte."
        )

    contract_months = get_int_setting("epargne.contract_months", 12)
    renewal_fee = Decimal(get_str_setting("epargne.renewal_fee", "5000"))
    today = timezone.localdate()
    now = timezone.now()

    # Trace du paiement des frais (pas un mouvement de solde — les frais sont
    # encaissés via Payment ; on écrit la ligne ledger pour pouvoir filtrer
    # « renouvellements payés ce mois » et auditer le cycle).
    ClassicSavingsTransaction.objects.create(
        account=locked,
        payment=None,
        type_op=ClassicSavingsTransaction.TypeOp.FRAIS_RENOUVELLEMENT,
        montant=renewal_fee,
        solde_apres=locked.solde,
        date=now,
    )

    previous_cycle = locked.cycle_courant
    locked.cycle_courant = previous_cycle + 1
    locked.date_prochaine_maturite = _add_months(today, contract_months)
    locked.statut_renouvellement = (
        ClassicSavingsAccount.StatutRenouvellement.ACTIF
    )
    locked.save(
        update_fields=[
            "cycle_courant",
            "date_prochaine_maturite",
            "statut_renouvellement",
            "updated_at",
        ]
    )

    record_audit(
        action="savings.renewed",
        entite_type="ClassicSavingsAccount",
        entite_id=locked.pk,
        user=paid_by,
        details={
            "member_id": locked.member_id,
            "previous_cycle": previous_cycle,
            "new_cycle": locked.cycle_courant,
            "new_maturity": locked.date_prochaine_maturite.isoformat(),
            "renewal_fee": str(renewal_fee),
            "paid_amount": str(paid_amount) if paid_amount is not None else None,
        },
    )

    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            "savings.renewed",
            member=locked.member,
            context={
                "prenom": locked.member.prenom,
                "numero_membre": locked.member.numero_membre,
                "new_cycle": locked.cycle_courant,
                "new_maturity": locked.date_prochaine_maturite.isoformat(),
                "renewal_fee": str(int(renewal_fee)),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("emit_event savings.renewed failed", exc_info=True)

    return locked
