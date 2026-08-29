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
from django.db.models import Sum
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    get_str_setting,
    record as record_audit,
)

from apps_coop.members.models import BookletOrder
from apps_coop.portal_urls import portal_url

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


def ensure_classic_maturity(account) -> None:
    """Garantit que le compte épargne classique porte une date de maturité.

    Le cron d'anniversaire (``epargne_anniversary_processing``) ne traite QUE
    les comptes dont ``date_prochaine_maturite`` n'est pas nul. Or la création
    organique d'un ``ClassicSavingsAccount`` (premier dépôt, bascule collecte)
    posait seulement ``date_ouverture`` → le cycle 12 mois ne s'amorçait jamais
    (aucune restitution, aucune ré-inscription). Ce helper pose la maturité à
    ``date_ouverture + epargne.contract_months`` au moment de la création.

    Idempotent : no-op si la date est déjà posée. Auto-réparateur : appelé sur
    un compte existant à maturité nulle (créé avant ce correctif), il l'initialise
    au prochain dépôt/bascule — une maturité déjà dépassée sera prise en charge
    par le cron dès son prochain passage.
    """
    if account.date_prochaine_maturite is not None:
        return
    from apps_coop.audit.services import get_int_setting

    contract_months = get_int_setting("epargne.contract_months", 12)
    account.date_prochaine_maturite = _add_months(
        account.date_ouverture, contract_months
    )
    account.save(update_fields=["date_prochaine_maturite", "updated_at"])


# Statuts d'un retrait ENGAGÉ (réservé) : la demande vit encore, l'argent est
# promis mais pas encore sorti du solde (le débit n'a lieu qu'au paiement). Ces
# montants sont « bloqués » — plus allouables ailleurs (2ᵉ retrait, garantie…)
# tant qu'ils ne sont pas payés (→ débités) ou rejetés (→ libérés).
_WITHDRAWAL_RESERVED_STATUSES = (
    WithdrawalRequest.Statut.EN_ATTENTE,
    WithdrawalRequest.Statut.APPROUVEE,
    WithdrawalRequest.Statut.EN_PAYOUT,
    WithdrawalRequest.Statut.PAYOUT_FAILED,
)


def reserved_withdrawals(
    *,
    classic_account: ClassicSavingsAccount | None = None,
    account: SavingsAccount | None = None,
    exclude_id: int | None = None,
) -> Decimal:
    """Somme des retraits ENGAGÉS (non payés, non rejetés) sur ce compte.

    C'est la part « réservée » : initiée/validée mais pas encore remise, donc
    pas encore débitée du solde. On la retranche du disponible pour qu'un même
    argent ne puisse pas être promis deux fois (``exclude_id`` sert à ignorer la
    demande elle-même quand on la ré-évalue à l'approbation)."""
    qs = WithdrawalRequest.objects.filter(statut__in=_WITHDRAWAL_RESERVED_STATUSES)
    if classic_account is not None:
        qs = qs.filter(classic_account=classic_account)
    else:
        qs = qs.filter(account=account)
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    # On réserve montant + frais_transaction : le débit au paiement prélève les
    # deux, donc le disponible doit déjà les bloquer (sinon un 2e retrait
    # pourrait promettre un argent qui servira à payer les frais du 1er).
    agg = qs.aggregate(m=Sum("montant"), f=Sum("frais_transaction"))
    return (agg["m"] or Decimal("0")) + (agg["f"] or Decimal("0"))


def _classic_retirable_raw(account: ClassicSavingsAccount) -> Decimal:
    """Part retirable AVANT réservation = solde − max(placement, gel garantie).

    Le placement est déjà bloqué (sous-canal CH-3). Le gel de garantie (caution
    avaliste + collatéral demandeur) « grise » en plus la part libre au-delà du
    placement. Ne retranche PAS les retraits en cours (voir ``classic_withdrawable``).
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


def classic_withdrawable(account: ClassicSavingsAccount) -> Decimal:
    """Part réellement disponible pour un NOUVEAU retrait classique.

    = ``_classic_retirable_raw`` − retraits déjà engagés (réservés) sur ce
    compte. Ainsi le solde total ne « ment » pas (il ne bouge qu'au paiement),
    mais le disponible reflète déjà ce qui est promis : impossible de re-retirer
    un montant déjà en attente/approuvé.
    """
    dispo = _classic_retirable_raw(account) - reserved_withdrawals(
        classic_account=account
    )
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
        # Disponible = solde − retraits déjà engagés (réservés) sur ce compte.
        disponible = Decimal(locked.solde) - reserved_withdrawals(account=locked)
        if disponible < 0:
            disponible = Decimal("0")
        account_kwargs = {"account": locked}
        pending_filter = {"account": locked}

    # Frais de transaction (%) prélevé EN PLUS, sur le solde (si l'admin a mis
    # « retrait » dans le périmètre) : l'épargne est débitée de montant + frais
    # au paiement, le membre reçoit montant. Le disponible doit couvrir les deux.
    from apps_coop.payments.fee_policy import OP_RETRAIT, transaction_fee_for

    frais = transaction_fee_for(montant, OP_RETRAIT)
    if montant + frais > disponible:
        raise ValueError(
            f"Montant demandé ({montant})"
            + (f" + {int(frais)} de frais" if frais > 0 else "")
            + f" supérieur au solde disponible ({disponible})."
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
        frais_transaction=frais,
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
                    "portal_url": portal_url(),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("withdrawal.requested email skipped", exc_info=True)

    # W2 — alerte STAFF : une demande de retrait attend une décision. Envoyée
    # à l'adresse ops configurable (AppSetting notifications.ops_email) ; no-op
    # si vide. Best-effort — ne casse jamais le flow.
    try:
        from django.conf import settings as dj_settings

        from apps_coop.audit.services import get_str_setting
        from apps_coop.notifications.events import emit_event

        ops = (get_str_setting("notifications.ops_email", "") or "").strip()
        if ops:
            emit_event(
                "withdrawal.admin_pending",
                member=member,  # contexte/prénom ; l'envoi part sur to_email (ops)
                to_email=ops,
                context={
                    "prenom": member.prenom,
                    "demandeur_nom": member.nom,
                    "demandeur_numero": member.numero_membre,
                    "montant": f"{int(montant):,}".replace(",", " "),
                    "source": source,
                    "admin_url": (
                        (get_str_setting("notifications.admin_url", "") or "").strip()
                        or getattr(dj_settings, "FRONTEND_BASE_URL", "")
                    ),
                },
            )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning("withdrawal.admin_pending staff alert skipped", exc_info=True)
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

    À l'**approbation**, on **ne débite PAS** le solde. L'argent reste dans le
    compte, seulement *engagé* (réservé — cf. ``reserved_withdrawals``) jusqu'au
    **paiement effectif**. On dissocie ainsi « demande initiée / validée » de
    « argent réellement sorti » : c'est ``mark_withdrawal_paid`` (remise espèces
    par le secrétaire) — ou le webhook payout (``_hook_decaissement``) — qui
    débite au moment où l'argent quitte réellement la caisse.

      1. Revérifie que la part retirable couvre encore le montant (garde contre
         un placement/gel survenu après la demande) — SANS toucher au solde.
      2. ``PRESENTIEL`` (ou MOMO payout Tara désactivé) → statut ``APPROUVEE`` ;
         l'admin cliquera « Confirmer remise » (``mark_withdrawal_paid``) qui
         **débite** et passe ``COMPLETEE``.
      3. ``MOMO`` + payout Tara activé → ``Payment(decaissement)`` + init payout,
         statut ``EN_PAYOUT`` ; le webhook **débite** et passe ``COMPLETEE``.

    **Note transaction** : volontairement pas ``@transaction.atomic`` global —
    l'appel HTTP Tara doit pouvoir laisser une trace ``payout_failed`` même si
    l'init payout lève une exception.
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

    # --- Approbation : PAS de débit. On vérifie seulement que la part retirable
    # couvre encore le montant (en excluant CETTE demande de la réserve, déjà
    # comptée). Le solde ne bougera qu'au paiement effectif. ---
    montant = Decimal(wr.montant)
    with transaction.atomic():
        if wr.source == WithdrawalRequest.Source.CLASSIQUE_LIBRE:
            cacc = ClassicSavingsAccount.objects.select_for_update().get(
                pk=wr.classic_account_id
            )
            disponible = _classic_retirable_raw(cacc) - reserved_withdrawals(
                classic_account=cacc, exclude_id=wr.id
            )
            if montant > disponible:
                raise ValueError(
                    f"Solde retirable insuffisant pour approuver : {disponible} "
                    f"< {montant} (placement bloqué + gel garantie crédit)."
                )
        else:
            account = SavingsAccount.objects.select_for_update().get(pk=wr.account_id)
            disponible = Decimal(account.solde) - reserved_withdrawals(
                account=account, exclude_id=wr.id
            )
            if montant > disponible:
                raise ValueError(
                    f"Solde insuffisant pour approuver : {disponible} < {montant}."
                )

        wr.decide_par = decided_by
        wr.date_decision = now
        # Payout Tara désactivé (défaut) → MOMO est traité comme le présentiel :
        # l'admin fait le virement sur Tara puis marque « payé » (mark-paid).
        from apps_coop.loans.services import tara_payout_enabled

        _auto_tara = (
            wr.mode_paiement == WithdrawalRequest.ModePaiement.MOMO
            and tara_payout_enabled()
        )
        if not _auto_tara:
            wr.statut = WithdrawalRequest.Statut.APPROUVEE
            wr.save(
                update_fields=["statut", "decide_par", "date_decision", "updated_at"]
            )
        else:
            # MOMO : reste EN_ATTENTE le temps de l'init payout ; le statut
            # EN_PAYOUT est posé par _init_payout_for_withdrawal.
            wr.save(update_fields=["decide_par", "date_decision", "updated_at"])

    record_audit(
        action="withdrawal.approved",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=decided_by,
        details={
            "montant": str(montant),
            "reserve": True,  # engagé (réservé), PAS encore débité
            "source": wr.source,
            "mode_paiement": wr.mode_paiement,
        },
    )

    # --- MOMO : init payout Tara hors transaction (uniquement si activé) ---
    if _auto_tara:
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
    from apps_coop.payments.providers import default_provider_code, get_provider
    from apps_coop.payments.providers.base import ProviderError

    # 1) Crée le Payment décaissement (atomique court)
    with transaction.atomic():
        payment = Payment.objects.create(
            member=wr.member,
            montant=wr.montant,
            type=Payment.Type.DECAISSEMENT,
            source=Payment.Source.MOBILE_MONEY,
            statut=Payment.Statut.EN_ATTENTE,
            provider_code=default_provider_code(),
            validated_by=decided_by,
            date_versement=timezone.now(),
            loan=None,
            idempotency_key=uuid.uuid4(),
        )
        wr.payout_payment = payment
        wr.save(update_fields=["payout_payment", "updated_at"])

    # 2) Appel provider hors transaction
    provider = get_provider(payment.provider_code or default_provider_code())
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


def _collecte_cash_payout_enabled() -> bool:
    """True si la restitution « cash » de la clôture collecte doit être
    décaissée automatiquement en Mobile Money (Tara).

    Défaut **FALSE** : tant que la coopérative ne l'active pas, la restitution
    reste une écriture au grand livre (retrait manuel au guichet, comportement
    historique). Piloté par l'AppSetting ``collecte.monthly.cash_payout``.
    """
    raw = get_str_setting("collecte.monthly.cash_payout", "false") or "false"
    return raw.strip().lower() in ("1", "true", "yes", "on")


def initiate_collecte_mobile_money_restitution(account, cash_txn, *, montant) -> None:
    """Traite le versement **Mobile Money** d'une restitution de clôture collecte.

    Déclenché quand le membre a choisi la préférence ``mobile_money`` et
    renseigné sa destination (``account.payout_phone`` + ``payout_network``).

    Deux régimes selon l'AppSetting ``collecte.monthly.cash_payout`` :

      - **OFF (défaut)** — versement **manuel** par la coopérative : on crée une
        ``WithdrawalRequest(MOMO, APPROUVEE)`` liée à la ligne de restitution,
        qui atterrit dans la file de payout admin. La coop exécute le transfert
        Mobile Money à la main puis marque « payé » (``mark_withdrawal_paid``).
      - **ON** — décaissement **automatique** via le provider (Tara).

    Sans destination renseignée (numéro vide) : on saute et on trace ; la
    restitution est alors à régulariser manuellement au guichet.

    Best-effort, jamais bloquant (appelé hors transaction du cron).
    """
    member = account.member
    phone = (
        (getattr(account, "payout_phone", "") or "")
        or (getattr(member, "phone", "") or "")
    ).strip()
    network = (getattr(account, "payout_network", "") or "").strip().upper()

    if not phone:
        record_audit(
            action="collecte.momo_restitution_skipped",
            entite_type="Member",
            entite_id=member.id,
            details={"reason": "no_destination", "montant": str(montant)},
        )
        return

    if _collecte_cash_payout_enabled():
        _auto_tara_collecte_payout(
            member, cash_txn, montant=montant, phone=phone, network=network
        )
    else:
        _queue_manual_collecte_payout(
            account, cash_txn, montant=montant, phone=phone, network=network
        )


def _queue_manual_collecte_payout(account, cash_txn, *, montant, phone, network) -> None:
    """Crée une demande de payout **APPROUVÉE** (versement manuel par la coop).

    La ``WithdrawalRequest`` réutilise la file de payout Mobile Money admin
    existante : la coopérative voit la demande, effectue le transfert à la main
    vers la destination renseignée par le membre, puis clique « payé ». On lie
    la ligne ``RESTITUTION_CASH`` déjà écrite (``cash_txn``) comme transaction de
    débit — le solde a déjà quitté la collecte, aucun double débit.
    """
    from apps_coop.savings.models import WithdrawalRequest

    net = network if network in WithdrawalRequest.Network.values else ""
    wr = WithdrawalRequest.objects.create(
        source=WithdrawalRequest.Source.COLLECTE,
        account=account,
        montant=montant,
        mode_paiement=WithdrawalRequest.ModePaiement.MOMO,
        recipient_phone=phone,
        network=net,
        statut=WithdrawalRequest.Statut.APPROUVEE,
        transaction=cash_txn,
        date_decision=timezone.now(),
        motif="Restitution fin de mois — collecte journalière",
    )
    phone_masked = phone[:4] + "***" + phone[-2:] if len(phone) >= 6 else "***"
    record_audit(
        action="collecte.momo_restitution_queued",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        details={
            "member_id": account.member_id,
            "montant": str(montant),
            "phone_masked": phone_masked,
            "network": net,
        },
    )


def _auto_tara_collecte_payout(member, cash_txn, *, montant, phone, network) -> None:
    """Décaisse **automatiquement** en Mobile Money (Tara) la restitution.

    - Lie le ``Payment`` à la ``SavingsTransaction`` RESTITUTION_CASH afin que
      le webhook de confirmation soit finalisé proprement (cf.
      ``payments.services._hook_decaissement``) — pas de « payout orphelin ».
    - Idempotent au niveau du mois via la garde ``already_closed`` du cron.
    """
    import uuid

    from django.conf import settings as dj_settings

    from apps_coop.payments.models import Payment
    from apps_coop.payments.providers import default_provider_code, get_provider
    from apps_coop.payments.providers.base import ProviderError

    # 1) Payment décaissement (le montant net 99 % restitué au membre).
    payment = Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.DECAISSEMENT,
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code=default_provider_code(),
        date_versement=timezone.now(),
        loan=None,
        idempotency_key=uuid.uuid4(),
    )
    if cash_txn is not None:
        try:
            cash_txn.payment = payment
            cash_txn.save(update_fields=["payment"])
        except Exception:  # noqa: BLE001
            logger.warning(
                "collecte cash payout : lien restitution↔payment échoué",
                exc_info=True,
            )

    # 2) Appel provider HORS de toute transaction du cron (échec = pas de
    #    rollback de la commission/restitution déjà commitées).
    provider = get_provider(payment.provider_code or default_provider_code())
    phone_masked = phone[:4] + "***" + phone[-2:] if len(phone) >= 6 else "***"
    try:
        result = provider.init_payout(payment, recipient_phone=phone, network=network)
    except ProviderError as exc:
        payment.statut = Payment.Statut.REJETE
        payment.motif_rejet = str(exc)[:500]
        payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
        record_audit(
            action="collecte.cash_payout_failed",
            entite_type="Member",
            entite_id=member.id,
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
    record_audit(
        action="collecte.cash_payout_initiated",
        entite_type="Member",
        entite_id=member.id,
        details={
            "payment_id": payment.id,
            "reference_externe": payment.reference_externe,
            "montant": str(montant),
            "phone_masked": phone_masked,
        },
    )

    # Mode recette : joue le webhook « valide » immédiatement.
    if getattr(dj_settings, "PAYMENTS_TEST_AUTO_VALIDATE", False):
        from apps_coop.payments.services import handle_webhook_event

        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference=payment.reference_externe,
            raw_payload={"auto_validate": True, "mode": "test", "kind": "collecte_payout"},
        )


@transaction.atomic
def apply_withdrawal_debit(wr: WithdrawalRequest, *, now=None) -> Decimal:
    """Débit EFFECTIF du solde au moment du paiement (remise espèces / payout
    complété). Crée la transaction ``RETRAIT`` et la lie à la ``wr``.

    Point unique de sortie d'argent d'un retrait — appelé par
    ``mark_withdrawal_paid`` (présentiel) et par le webhook payout
    (``_hook_decaissement``). **Idempotent** : si la WR a déjà une transaction
    liée (déjà débitée), ne re-débite pas. Renvoie le nouveau solde.
    """
    now = now or timezone.now()
    montant = Decimal(wr.montant)
    # Débit RÉEL = montant + frais de transaction : le membre reçoit `montant`,
    # la coopérative encaisse `frais`. La transaction ledger porte le total sorti
    # du solde. `frais` = 0 tant que le retrait n'est pas dans le périmètre.
    frais = Decimal(wr.frais_transaction or 0)
    total = montant + frais
    if wr.source == WithdrawalRequest.Source.CLASSIQUE_LIBRE:
        if wr.classic_transaction_id:  # déjà débité → idempotent
            return Decimal(wr.classic_account.solde)
        cacc = ClassicSavingsAccount.objects.select_for_update().get(
            pk=wr.classic_account_id
        )
        if total > Decimal(cacc.solde):
            raise ValueError(
                f"Solde classique insuffisant au paiement : {cacc.solde} < {total}."
            )
        nouveau_solde = Decimal(cacc.solde) - total
        cacc.solde = nouveau_solde
        cacc.save(update_fields=["solde", "updated_at"])
        ctx = ClassicSavingsTransaction.objects.create(
            account=cacc,
            payment=None,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=total,
            solde_apres=nouveau_solde,
            date=now,
            # Rattacher l'écriture de retrait au carnet du membre (comme le
            # dépôt) : dans le carnet papier, dépôts ET retraits vivent dans le
            # même carnet. Sans ça, le retrait n'apparaissait sur aucun carnet.
            booklet_order=BookletOrder.latest_for(cacc.member),
        )
        wr.classic_transaction = ctx
        wr.save(update_fields=["classic_transaction", "updated_at"])
    else:
        if wr.transaction_id:  # déjà débité → idempotent
            return Decimal(wr.account.solde)
        account = SavingsAccount.objects.select_for_update().get(pk=wr.account_id)
        if total > Decimal(account.solde):
            raise ValueError(
                f"Solde collecte insuffisant au paiement : {account.solde} < {total}."
            )
        nouveau_solde = Decimal(account.solde) - total
        account.solde = nouveau_solde
        account.save(update_fields=["solde", "updated_at"])
        tx = SavingsTransaction.objects.create(
            account=account,
            payment=None,
            type_op=SavingsTransaction.TypeOp.RETRAIT,
            montant=total,
            solde_apres=nouveau_solde,
            date=now,
            # Cf. ci-dessus : le retrait s'impute au carnet du membre, comme le
            # dépôt (même carnet papier pour les deux sens).
            booklet_order=BookletOrder.latest_for(account.member),
        )
        wr.transaction = tx
        wr.save(update_fields=["transaction", "updated_at"])
    return nouveau_solde


def mark_withdrawal_paid(
    wr: WithdrawalRequest,
    *,
    agent,
    note: str = "",
) -> WithdrawalRequest:
    """Marque un retrait comme remis — c'est ICI que le solde est **débité**.

    Précondition : statut == ``APPROUVEE``. Le secrétaire remet l'argent puis
    confirme : on débite réellement le solde (``apply_withdrawal_debit``) et on
    passe ``COMPLETEE``. Idempotent : si déjà ``COMPLETEE``, renvoie tel quel.
    S'applique au présentiel (espèces) ET au MOMO réglé à la main sur Tara.
    """
    if wr.statut == WithdrawalRequest.Statut.COMPLETEE:
        return wr  # idempotent

    if wr.statut != WithdrawalRequest.Statut.APPROUVEE:
        raise ValueError(
            f"Statut {wr.statut!r} — seul un retrait approuvé peut être marqué remis."
        )

    now = timezone.now()
    with transaction.atomic():
        nouveau_solde = apply_withdrawal_debit(wr, now=now)
        wr.statut = WithdrawalRequest.Statut.COMPLETEE
        wr.handed_over_by = agent
        wr.handed_over_at = now
        wr.save(
            update_fields=["statut", "handed_over_by", "handed_over_at", "updated_at"]
        )

    record_audit(
        action="withdrawal.handed_over",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=agent,
        details={"note": note[:200], "solde_apres": str(nouveau_solde)},
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
    mais réutilise la même ``WithdrawalRequest``. Le solde n'est PAS encore
    débité (il ne l'est qu'à la complétion du payout) — rien à rembourser.
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
                "portal_url": portal_url(),
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
        booklet_order=BookletOrder.latest_for(locked.member),
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
