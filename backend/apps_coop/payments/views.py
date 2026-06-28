"""HTTP entry points for the payments domain.

Three production endpoints wire the validated flow
(`architecture/01-paiement-mobile-money-tara.md`):

  - ``POST /api/v1/payments/init/``           — member starts a payment
  - ``GET  /api/v1/payments/{id}/``           — portal polls for the current status
  - ``POST /api/v1/payments/webhook/tara/``   — Tara → us, signed HMAC

Plus one dev-only endpoint:

  - ``POST /api/v1/payments/dev/<id>/confirm/``   — simulate a successful Tara
    webhook locally (DEBUG only)

The views stay thin — heavy lifting is delegated to ``services.py``.
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import IsAdmin, IsMember, IsStaff

from .models import FeeType, Payment, RateParam
from .providers import get_provider
from .providers.base import ProviderError
from .serializers import PaymentInitSerializer, PaymentReadSerializer
from .services import handle_webhook_event, init_payin_for_payment


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. POST /api/v1/payments/init/  — member starts a payment
# ---------------------------------------------------------------------------


_TYPES_ALLOWED_FOR_SUSPENDED = {
    Payment.Type.FRAIS_ADHESION,
    Payment.Type.FRAIS_INSCRIPTION,
    # CH-2 . Le 3eme frais d'activation (carnet) doit pouvoir etre paye en
    # statut SUSPENDU . sinon la transition SUSPENDU . ACTIF ne se declenche
    # jamais (_membership_fees_settled exige les 3 frais VALIDE). Idem pour
    # le renouvellement annuel D6 (FRAIS_CARNET avec is_renewal=True) ou le
    # membre est SUSPENDU apres la fenetre de grace.
    Payment.Type.FRAIS_CARNET,
}


@extend_schema(
    tags=["payments"],
    summary="Initie un paiement Mobile Money",
    description=(
        "Crée un `Payment` en attente, appelle le provider (Tara) pour pousser le "
        "USSD au téléphone, et retourne le `paymentId` à utiliser pour le polling.\n\n"
        "Types acceptés : `epargne`, `frais_adhesion`, `frais_inscription`, "
        "`frais_demande_credit`, `frais_carnet`, `remboursement`.\n\n"
        "**Restrictions** :\n"
        "- Membre `suspendu` → uniquement `frais_adhesion` / `frais_inscription`\n"
        "- Type `remboursement` → `loan_id` requis, doit appartenir au membre, "
        "  montant ≤ `Loan.solde_restant`"
    ),
    request=PaymentInitSerializer,
    responses={
        201: OpenApiResponse(description="`{ payment, paymentUrl, instructions }`"),
        400: OpenApiResponse(description="Validation rejetée (montant, loan_id, etc.)"),
        403: OpenApiResponse(description="Statut membre incompatible avec le type"),
        404: OpenApiResponse(description="Loan introuvable (cas remboursement)"),
        502: OpenApiResponse(description="Provider erreur non-réessayable"),
        503: OpenApiResponse(description="Provider indisponible (retryable)"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
def init_payment(request):
    serializer = PaymentInitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    member = request.user.member
    # Suspended members may only pay their 1st cotisation (frais_adhesion /
    # frais_inscription). Everything else requires `actif`.
    if member.statut == "suspendu" and data["type"] not in _TYPES_ALLOWED_FOR_SUSPENDED:
        return Response(
            {
                "detail": (
                    "Compte membre suspendu — seuls les frais d'adhésion, "
                    "d'inscription et de carnet sont autorisés tant que "
                    "l'activation n'est pas faite."
                )
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # For repayments, the Loan must exist, belong to the member, and the
    # amount must not exceed what's still owed (anti-surplus).
    if data["type"] == Payment.Type.REMBOURSEMENT:
        from apps_coop.loans.models import Loan  # local — avoid cycle

        loan_id = data.get("loan_id")
        if loan_id is None:
            return Response(
                {"detail": "loan_id requis pour un remboursement."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            loan = Loan.objects.get(pk=loan_id, member=member)
        except Loan.DoesNotExist:
            return Response(
                {"detail": "Ce crédit n'existe pas ou ne t'appartient pas."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if loan.statut not in (Loan.Statut.ACTIF, Loan.Statut.EN_RETARD):
            return Response(
                {"detail": f"Crédit en statut {loan.statut!r} — remboursement impossible."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data["montant"] > loan.solde_restant:
            return Response(
                {
                    "detail": (
                        f"Montant supérieur au solde restant ({loan.solde_restant} XAF). "
                        "Réduis le montant pour éviter un trop-perçu."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # LOT 6 (refonte 2026) — multi-jours pré-payé sur la collecte journalière.
    # On valide ici car la sérialisation n'a pas accès aux AppSettings.
    nb_jours = data.get("nb_jours_couverts", 1) or 1
    # TODO: REMOVE_FOR_PROD — bypass montant pour tester STK Push réel.
    _test_any_amount = getattr(settings, "PAYMENTS_TEST_ALLOW_ANY_AMOUNT", False)
    if data["type"] == Payment.Type.EPARGNE and nb_jours != 1:
        from apps_coop.audit.services import get_int_setting

        min_per_day = get_int_setting("collecte.min_per_day", 1000)
        max_days = get_int_setting("collecte.prepay.max_days", 30)
        if nb_jours > max_days:
            return Response(
                {
                    "detail": (
                        f"Mode multi-jours plafonné à {max_days} jours "
                        f"(reçu {nb_jours})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        expected = nb_jours * min_per_day
        if not _test_any_amount and data["montant"] != expected:
            return Response(
                {
                    "detail": (
                        f"Mode multi-jours : montant attendu "
                        f"{nb_jours} × {min_per_day} = {expected} FCFA "
                        f"(reçu {int(data['montant'])})."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif data["type"] != Payment.Type.EPARGNE and nb_jours != 1:
        return Response(
            {
                "detail": (
                    "nb_jours_couverts > 1 n'est valide que pour le type "
                    "'epargne' (collecte journalière)."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Épargne classique : produit dissocié de la cotisation, piloté par une
    # config admin (ouverture + bornes de dépôt). Règles fines à venir.
    if data["type"] == Payment.Type.EPARGNE_CLASSIQUE:
        from apps_coop.savings.models import ClassicSavingsConfig

        cfg = ClassicSavingsConfig.get_solo()
        if not cfg.actif:
            return Response(
                {"detail": "L'épargne classique n'est pas ouverte aux dépôts pour le moment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # TODO: REMOVE_FOR_PROD — bypass min/max pour tester STK Push réel.
        if not _test_any_amount and data["montant"] < cfg.depot_min:
            return Response(
                {"detail": f"Dépôt minimum : {int(cfg.depot_min)} XAF."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            not _test_any_amount
            and cfg.depot_max is not None
            and data["montant"] > cfg.depot_max
        ):
            return Response(
                {"detail": f"Dépôt maximum : {int(cfg.depot_max)} XAF."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # CH-3 — placement valable uniquement sur EPARGNE_CLASSIQUE.
    is_placement = bool(data.get("is_placement", False)) and (
        data["type"] == Payment.Type.EPARGNE_CLASSIQUE
    )

    # O4 . Anti double-tap . si l'utilisateur tape 'Payer' 2 fois en moins
    # de N secondes (defaut 30s, tunable payments.init.dedup_window_seconds),
    # on reutilise le Payment EN_ATTENTE existant pour ne pas declencher 2
    # STK Push simultanes. Identite : (member, type, montant, loan_id,
    # loan_installment_id, nb_jours_couverts). Strict, donc des montants
    # differents creent bien 2 paiements.
    try:
        from apps_coop.audit.services import get_int_setting
        dedup_window = get_int_setting(
            "payments.init.dedup_window_seconds", 30,
        )
    except Exception:  # noqa: BLE001
        dedup_window = 30
    if dedup_window > 0:
        from datetime import timedelta
        dedup_cutoff = timezone.now() - timedelta(seconds=dedup_window)
        existing = (
            Payment.objects.filter(
                member=request.user.member,
                type=data["type"],
                montant=data["montant"],
                statut=Payment.Statut.EN_ATTENTE,
                source=Payment.Source.MOBILE_MONEY,
                created_at__gte=dedup_cutoff,
                loan_id=data.get("loan_id"),
                loan_installment_id=data.get("loan_installment_id"),
                nb_jours_couverts=nb_jours,
            )
            .order_by("-created_at")
            .first()
        )
        if existing is not None:
            record_audit(
                action="payment.init.dedup_hit",
                entite_type="Payment",
                entite_id=existing.id,
                user=request.user,
                details={
                    "window_seconds": dedup_window,
                    "type": data["type"],
                    "montant": str(data["montant"]),
                },
            )
            # PaymentReadSerializer est deja importe ligne 40. Un import
            # local masquerait le scope global et provoquerait
            # UnboundLocalError quand la fonction l'utilise plus bas.
            return Response(
                PaymentReadSerializer(existing).data,
                status=status.HTTP_200_OK,
            )

    payment = Payment.objects.create(
        member=request.user.member,
        montant=data["montant"],
        type=data["type"],
        source=Payment.Source.MOBILE_MONEY,
        statut=Payment.Statut.EN_ATTENTE,
        provider_code="tara",
        date_versement=timezone.now(),
        loan_id=data.get("loan_id"),
        loan_installment_id=data.get("loan_installment_id"),
        nb_jours_couverts=nb_jours,
        is_placement=is_placement,
    )

    try:
        payment_url, provider_reference, provider_raw = init_payin_for_payment(
            payment,
            phone=data["phone"],
            network=data["network"],
        )
        payment.save(update_fields=["reference_externe", "gateway_initiated_at", "updated_at"])
        # Mode recette flows complets — auto-validate (cf. settings).
        # Bypass de Tara : on joue immédiatement le webhook "valide" en local
        # afin que les hooks métier (`_hook_savings_deposit`, `_hook_remboursement`,
        # etc.) tournent et que l'UI voie la transaction reflétée.
        if getattr(settings, "PAYMENTS_TEST_AUTO_VALIDATE", False):
            handle_webhook_event(
                payment.idempotency_key,
                "valide",
                provider_reference=provider_reference,
                raw_payload={"auto_validate": True, "mode": "test"},
            )
            payment.refresh_from_db()
    except ProviderError as exc:
        payment.statut = Payment.Statut.REJETE
        payment.motif_rejet = str(exc)[:500]
        payment.save(update_fields=["statut", "motif_rejet", "updated_at"])
        record_audit(
            action="payment.init.failed",
            entite_type="Payment",
            entite_id=payment.id,
            user=request.user,
            details={"reason": str(exc), "retryable": exc.retryable},
            ip=client_ip(request),
        )
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_502_BAD_GATEWAY
        )
        return Response(
            {"detail": "Service de paiement indisponible. Réessaie dans quelques instants."},
            status=http_status,
        )

    record_audit(
        action="payment.init",
        entite_type="Payment",
        entite_id=payment.id,
        user=request.user,
        details={
            "type": payment.type,
            "montant": str(payment.montant),
            "provider": payment.provider_code,
            "network": data["network"],
        },
        ip=client_ip(request),
    )
    # Notif in-app "Paiement en cours" — visible immediatement par le membre
    # meme s'il ne valide pas le STK Push (cas frequent ou Payment reste en
    # en_attente). Voir notify_payment_initiated dans services.
    from .services import notify_payment_initiated

    if payment.statut == Payment.Statut.EN_ATTENTE:
        notify_payment_initiated(payment)
    # Expose `provider_status` / `provider_message` / `provider_vendor`
    # côté mobile pour qu'il affiche le statut Tara reçu (utile quand le
    # STK Push ne semble pas arriver — on peut voir si Tara a accepté
    # ORANGE_CAMEROON / MTN_CAMEROON, ou un message d'erreur explicite).
    return Response(
        {
            "payment": PaymentReadSerializer(payment).data,
            "paymentUrl": payment_url,
            "instructions": "Valide la transaction sur ton téléphone via le code USSD reçu.",
            "providerStatus": provider_raw.get("status"),
            "providerMessage": provider_raw.get("message"),
            "providerVendor": provider_raw.get("vendor"),
        },
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# 2. GET /api/v1/payments/{id}/  — portal polls for the status
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="État d'un paiement",
    description="Polling par le portail : `en_attente` → `valide` ou `rejete`.",
    responses={200: PaymentReadSerializer, 404: OpenApiResponse(description="Pas le payment du membre")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def payment_detail(request, pk: int):
    try:
        payment = Payment.objects.get(pk=pk, member=request.user.member)
    except Payment.DoesNotExist:
        return Response({"detail": "Paiement introuvable."}, status=status.HTTP_404_NOT_FOUND)
    return Response(PaymentReadSerializer(payment).data)


# ---------------------------------------------------------------------------
# 2b. GET /api/v1/payments/me/  — historique des paiements du membre
#     (page « Mes cotisations » côté portail + mobile)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="Mes paiements (historique membre)",
    description=(
        "Renvoie les paiements du membre connecté, les plus récents d'abord. "
        "Filtre optionnel `?type=` (epargne / frais_adhesion / frais_inscription / "
        "frais_demande_credit / frais_reconduction / frais_carnet / remboursement). "
        "Limité aux 100 dernières lignes."
    ),
    responses={200: PaymentReadSerializer(many=True)},
)
@api_view(["GET"])
@permission_classes([IsMember])
def payments_me(request):
    qs = Payment.objects.filter(member=request.user.member).order_by(
        "-date_versement", "-id"
    )
    type_filter = (request.query_params.get("type") or "").strip()
    if type_filter:
        qs = qs.filter(type=type_filter)
    qs = qs[:100]  # garde-fou identique à notifications
    return Response({"results": PaymentReadSerializer(qs, many=True).data})


# ---------------------------------------------------------------------------
# 3. POST /api/v1/payments/webhook/tara/  — Tara → us
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="Webhook entrant de Tara (signé HMAC)",
    description=(
        "Reçoit la confirmation de paiement de Tara. L'en-tête `X-Tara-Signature` "
        "(HMAC SHA-256 du body avec `TARA_WEBHOOK_SECRET`) authentifie la requête. "
        "Aucune session Django. Idempotent : un même `productId` traité 2× = no-op."
    ),
    responses={
        200: OpenApiResponse(description="ack — événement traité ou no-op"),
        401: OpenApiResponse(description="Signature HMAC invalide"),
        404: OpenApiResponse(description="`productId` inconnu (pas un de nos Payments)"),
    },
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook_tara(request):
    """Tara webhook receiver. The HMAC header authenticates the request — no
    Django session involved on purpose.
    """
    signature = request.headers.get("X-Tara-Signature", "")
    provider = get_provider("tara")

    try:
        event = provider.verify_webhook(request.body, signature)
    except ProviderError as exc:
        record_audit(
            action="payment.webhook.rejected",
            entite_type="Payment",
            details={"provider": "tara", "reason": str(exc)},
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

    # Log explicite de ce qu'on a parse (utile pour debug en prod quand
    # Tara envoie un payload inattendu) -- on masque rien, c'est cote
    # serveur uniquement.
    logger.info(
        "[TARA] webhook OK — key=%r status=%r ref=%r raw=%s",
        event.payment_idempotency_key,
        event.status,
        event.provider_reference,
        event.raw,
    )
    payment = None
    try:
        payment = handle_webhook_event(
            event.payment_idempotency_key,
            event.status,
            provider_reference=event.provider_reference,
            raw_payload=event.raw,
        )
    except Payment.DoesNotExist:
        record_audit(
            action="payment.webhook.unknown_payment",
            entite_type="Payment",
            details={"provider": "tara", "key": event.payment_idempotency_key},
            ip=client_ip(request),
        )
        return Response({"detail": "Paiement inconnu."}, status=status.HTTP_404_NOT_FOUND)
    except NotImplementedError as exc:
        # Business hook not wired yet — we still ack so Tara doesn't retry,
        # but we log loudly for the maintainer.
        logger.exception("Webhook business hook missing: %s", exc)
    except Exception as exc:
        # Filet de securite : on ne veut PAS qu'un bug interne renvoie 500
        # a Tara (ils ne retry pas, mais on perd la trace de la transaction).
        # On log la stack complete et on ack avec un 200 contenant le diagnostic.
        logger.exception(
            "[TARA] webhook handler crashed for key=%r status=%r: %s",
            event.payment_idempotency_key, event.status, exc,
        )
        record_audit(
            action="payment.webhook.handler_error",
            entite_type="Payment",
            details={
                "provider": "tara",
                "key": event.payment_idempotency_key,
                "error": str(exc)[:300],
            },
            ip=client_ip(request),
        )
        return Response(
            {"ok": False, "error": "handler_error", "detail": str(exc)[:200]},
            status=status.HTTP_200_OK,  # 200 pour que Tara ne retry pas
        )

    return Response({"ok": True, "status": payment.statut if payment else "unknown"})


# ---------------------------------------------------------------------------
# Bonus — GET /api/v1/payments/fees/   (read FeeType for the portal)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="Catalogue des frais administratifs",
    description=(
        "Retourne les frais actifs depuis `FeeType` (admin-editable), indexés par "
        "code. Codes possibles : `INSCRIPTION`, `ADHESION`, `DEMANDE_CREDIT`, "
        "`RECONDUCTION`, `CARNET`."
    ),
    responses={200: OpenApiResponse(description="`{ 'ADHESION': {libelle, montant}, ... }`")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def list_fees(request):
    """Return the current administrative fees (FeeType.actif=True) as a
    code-indexed dict, e.g. ``{"ADHESION": "5000.00", "DEMANDE_CREDIT": "5000.00", …}``.

    Used by the portal to display the 1st-cotisation amount on the activation
    screen, or the loan request fee before submission. The admin edits these
    rows in ``/django-admin/payments/feetype/`` — no deploy needed.
    """
    fees = {
        fee.code: {"libelle": fee.libelle, "montant": str(fee.montant)}
        for fee in FeeType.objects.filter(actif=True)
    }
    return Response(fees)


# ---------------------------------------------------------------------------
# Coûts modifiables (BR2) — taux métier + édition admin protégée
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="Catalogue des taux métier",
    description=(
        "Retourne les taux actifs depuis `RateParam` (admin-editable), indexés "
        "par code. `valeur` est un ratio (ex. `0.1000` = 10 %). Codes : "
        "`LOAN_INTEREST`, `SAVINGS_INTEREST_MONTHLY`, `RENEWAL_CASH`, "
        "`RENEWAL_DEFERRED`, `LATE_PENALTY`."
    ),
    responses={200: OpenApiResponse(description="`{ 'LOAN_INTEREST': {libelle, valeur}, ... }`")},
)
@api_view(["GET"])
@permission_classes([IsMember])
def list_rates(request):
    """Taux métier courants (RateParam.actif=True), indexés par code.

    Lecture seule, exposée au portail/mobile pour afficher les pourcentages
    réellement appliqués. L'admin les édite via les endpoints `admin/`.
    """
    rates = {
        rate.code: {"libelle": rate.libelle, "valeur": str(rate.valeur)}
        for rate in RateParam.objects.filter(actif=True)
    }
    return Response(rates)


@extend_schema(
    tags=["payments"],
    summary="Config des coûts (admin) — frais + taux",
    description=(
        "Vue staff : retourne TOUS les `FeeType` et `RateParam` (actifs ou non) "
        "pour l'écran d'édition des coûts. Alimente la page admin Next.js."
    ),
    responses={200: OpenApiResponse(description="`{ fees: FeeType[], rates: RateParam[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_config(request):
    fees = [
        {
            "code": f.code,
            "libelle": f.libelle,
            "montant": str(f.montant),
            "actif": f.actif,
        }
        for f in FeeType.objects.all()
    ]
    rates = [
        {
            "code": r.code,
            "libelle": r.libelle,
            "valeur": str(r.valeur),
            "actif": r.actif,
        }
        for r in RateParam.objects.all()
    ]
    return Response({"fees": fees, "rates": rates})


@extend_schema(
    tags=["payments"],
    summary="Éditer un frais (admin)",
    description=(
        "PATCH staff : met à jour le `montant` (≥ 0), et optionnellement "
        "`libelle` / `actif`, d'un `FeeType` identifié par son code. Tracé en "
        "audit (`config.fee_updated`)."
    ),
    responses={200: OpenApiResponse(description="Le FeeType mis à jour.")},
)
@api_view(["PATCH"])
@permission_classes([IsStaff])
def admin_update_fee(request, code: str):
    try:
        fee = FeeType.objects.get(code=code)
    except FeeType.DoesNotExist:
        return Response({"detail": f"Frais inconnu : {code}"}, status=status.HTTP_404_NOT_FOUND)

    updated = []
    if "montant" in request.data:
        try:
            montant = Decimal(str(request.data["montant"]))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Montant invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if montant < 0:
            return Response({"detail": "Le montant doit être ≥ 0."}, status=status.HTTP_400_BAD_REQUEST)
        fee.montant = montant
        updated.append("montant")
    if "libelle" in request.data:
        fee.libelle = str(request.data["libelle"])[:120]
        updated.append("libelle")
    if "actif" in request.data:
        fee.actif = bool(request.data["actif"])
        updated.append("actif")

    if not updated:
        return Response({"detail": "Rien à mettre à jour."}, status=status.HTTP_400_BAD_REQUEST)

    fee.save(update_fields=[*updated, "updated_at"])
    record_audit(
        action="config.fee_updated",
        entite_type="FeeType",
        entite_id=fee.pk,
        user=request.user,
        details={"code": fee.code, "champs": updated, "montant": str(fee.montant)},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(
        {"code": fee.code, "libelle": fee.libelle, "montant": str(fee.montant), "actif": fee.actif}
    )


@extend_schema(
    tags=["payments"],
    summary="Éditer un taux (admin)",
    description=(
        "PATCH staff : met à jour la `valeur` (ratio entre 0 et 1), et "
        "optionnellement `libelle` / `actif`, d'un `RateParam` identifié par "
        "son code. Tracé en audit (`config.rate_updated`)."
    ),
    responses={200: OpenApiResponse(description="Le RateParam mis à jour.")},
)
@api_view(["PATCH"])
@permission_classes([IsStaff])
def admin_update_rate(request, code: str):
    try:
        rate = RateParam.objects.get(code=code)
    except RateParam.DoesNotExist:
        return Response({"detail": f"Taux inconnu : {code}"}, status=status.HTTP_404_NOT_FOUND)

    updated = []
    if "valeur" in request.data:
        try:
            valeur = Decimal(str(request.data["valeur"]))
        except (InvalidOperation, TypeError):
            return Response({"detail": "Valeur invalide."}, status=status.HTTP_400_BAD_REQUEST)
        if not (Decimal("0") <= valeur <= Decimal("1")):
            return Response(
                {"detail": "Le taux doit être un ratio entre 0 et 1 (ex. 0.10 = 10 %)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        rate.valeur = valeur
        updated.append("valeur")
    if "libelle" in request.data:
        rate.libelle = str(request.data["libelle"])[:120]
        updated.append("libelle")
    if "actif" in request.data:
        rate.actif = bool(request.data["actif"])
        updated.append("actif")

    if not updated:
        return Response({"detail": "Rien à mettre à jour."}, status=status.HTTP_400_BAD_REQUEST)

    rate.save(update_fields=[*updated, "updated_at"])
    record_audit(
        action="config.rate_updated",
        entite_type="RateParam",
        entite_id=rate.pk,
        user=request.user,
        details={"code": rate.code, "champs": updated, "valeur": str(rate.valeur)},
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    return Response(
        {"code": rate.code, "libelle": rate.libelle, "valeur": str(rate.valeur), "actif": rate.actif}
    )


# ---------------------------------------------------------------------------
# 4. POST /api/v1/payments/dev/<pk>/confirm/  — DEV ONLY (simulate webhook)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["payments"],
    summary="🛠️ Dev only — simule la confirmation Tara",
    description=(
        "Bypass complet du provider et du HMAC. Appelle directement `handle_webhook_event(idempotency_key, \"valide\")`. "
        "Disponible **uniquement** quand `settings.DEBUG=True` ; renvoie 404 en prod. "
        "Utilisé tant qu'on n'a pas les clés Tara sandbox."
    ),
    responses={
        200: PaymentReadSerializer,
        400: OpenApiResponse(description="Payment déjà traité"),
        404: OpenApiResponse(description="Payment introuvable / pas le membre / pas en DEBUG"),
    },
)
@api_view(["POST"])
@permission_classes([IsMember])
def dev_confirm_payment(request, pk: int):
    """Simulate a successful Tara webhook locally — bypasses HMAC and the
    actual provider. Active **uniquement** quand ``settings.DEBUG = True`` :
    en production, retourne 404.

    Le membre ne peut confirmer que ses propres paiements. Utile tant qu'on
    n'a pas les clés Tara sandbox — voir bouton « DEV — Simuler » dans le
    portail.
    """
    if not settings.DEBUG:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        payment = Payment.objects.get(pk=pk, member=request.user.member)
    except Payment.DoesNotExist:
        return Response({"detail": "Paiement introuvable."}, status=status.HTTP_404_NOT_FOUND)

    if payment.statut != Payment.Statut.EN_ATTENTE:
        return Response(
            {"detail": f"Paiement déjà en statut {payment.statut!r}, rien à simuler."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        handle_webhook_event(
            payment.idempotency_key,
            "valide",
            provider_reference=payment.reference_externe or f"DEV-SIM-{payment.id}",
            raw_payload={"dev_simulation": True},
        )
    except NotImplementedError as exc:
        return Response(
            {"detail": f"Aucun hook métier implémenté pour {payment.type!r}: {exc}"},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    record_audit(
        action="payment.dev.simulated",
        entite_type="Payment",
        entite_id=payment.id,
        user=request.user,
        details={"type": payment.type, "montant": str(payment.montant)},
        ip=client_ip(request),
    )
    payment.refresh_from_db()
    return Response(PaymentReadSerializer(payment).data)


# ---------------------------------------------------------------------------
# Admin endpoints — Next.js admin dashboard
# ---------------------------------------------------------------------------


_ADMIN_PAYMENTS_PAGE_SIZE = 200


@extend_schema(
    tags=["payments"],
    summary="🔒 Staff — liste des paiements",
    description=(
        "Liste paginée des derniers paiements pour le dashboard admin.\n\n"
        "Filtres : `?statut=en_attente|valide|rejete|annule`, "
        "`?type=epargne|frais_adhesion|...`, `?member=<id>`, `?q=<numero_membre|ref>`."
    ),
    responses={200: OpenApiResponse(description="`{ count, results: Payment[] }`")},
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_payments(request):
    qs = Payment.objects.select_related("member").order_by("-date_versement")
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    type_filter = request.query_params.get("type")
    if type_filter:
        qs = qs.filter(type=type_filter)
    member_id = request.query_params.get("member")
    if member_id:
        qs = qs.filter(member_id=member_id)
    q = (request.query_params.get("q") or "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(member__numero_membre__icontains=q)
            | Q(member__nom__icontains=q)
            | Q(member__prenom__icontains=q)
            | Q(reference_externe__icontains=q)
        )

    from apps_coop.common import parse_pagination

    offset, limit = parse_pagination(
        request, default_limit=25, max_limit=_ADMIN_PAYMENTS_PAGE_SIZE
    )
    count = qs.count()
    rows = qs[offset : offset + limit]
    # Enrich with member display so the admin table doesn't need a second call.
    results = []
    for p in rows:
        data = PaymentReadSerializer(p).data
        data["member"] = {
            "id": p.member_id,
            "numero_membre": p.member.numero_membre,
            "nom": p.member.nom,
            "prenom": p.member.prenom,
        }
        results.append(data)
    return Response(
        {"count": count, "limit": limit, "offset": offset, "results": results}
    )


# ---------------------------------------------------------------------------
# B1 . Saisie versement agence (cash-in) par admin
# ---------------------------------------------------------------------------
# L'admin recoit un versement physique au comptoir et l'enregistre depuis
# le dashboard. Cree un Payment(source=MANUEL, statut=VALIDE) puis appelle
# directement le hook business correspondant au type (pas de webhook Tara).
#
# Permission : IsAdmin (plus strict que IsStaff . groupe "admin" uniquement,
# financier sensible). validated_by stocke l'admin saisisseur. Audit
# "payment.cash_in_admin" obligatoire avec montant, type, membre cible.
#
# Types autorises (whitelist) :
#   . FRAIS_ADHESION / FRAIS_INSCRIPTION / FRAIS_CARNET . frais d'adhesion 13k
#   . FRAIS_DEMANDE_CREDIT . frais d'etude credit (CH-7)
#   . EPARGNE . cotisation journaliere (multi-jours via nb_jours_couverts)
#   . EPARGNE_CLASSIQUE . depot classique (libre via is_placement=False ou
#     placement via is_placement=True)
#   . REMBOURSEMENT . remboursement credit (loan_id obligatoire)
# Types interdits : DECAISSEMENT (passe par /loans/admin/disburse-now/),
# FRAIS_RECONDUCTION (reconduction gratuite Art.10/11).

_CASH_IN_ALLOWED_TYPES = {
    Payment.Type.FRAIS_ADHESION,
    Payment.Type.FRAIS_INSCRIPTION,
    Payment.Type.FRAIS_CARNET,
    Payment.Type.FRAIS_DEMANDE_CREDIT,
    Payment.Type.EPARGNE,
    Payment.Type.EPARGNE_CLASSIQUE,
    Payment.Type.REMBOURSEMENT,
}


@extend_schema(
    tags=["payments"],
    summary="🔒 Admin — Saisir un versement reçu en agence (cash-in)",
    description=(
        "Permission : `IsAdmin` (groupe `admin` strict). Cree un Payment "
        "`source=MANUEL`, `statut=VALIDE` immediatement et declenche le hook "
        "business du type correspondant (activation membre, depot epargne, "
        "imputation remboursement, etc.). Champs : `member_id`, `type`, "
        "`montant` requis. `reference_externe` (n° bordereau papier) "
        "fortement recommande. `note` libre. Specifiques : `loan_id` si "
        "REMBOURSEMENT, `nb_jours_couverts` (>=1) si EPARGNE multi-jours, "
        "`is_placement` (bool) si EPARGNE_CLASSIQUE."
    ),
    responses={
        200: OpenApiResponse(description="Payment cree et hook business execute"),
        400: OpenApiResponse(description="Donnees invalides"),
        403: OpenApiResponse(description="Pas admin"),
        404: OpenApiResponse(description="Membre ou crédit introuvable"),
    },
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_cash_in_payment(request):
    """Saisie versement agence . cree Payment MANUEL/VALIDE + execute hook."""
    from django.db import transaction as db_transaction
    from apps_coop.members.models import Member

    data = request.data or {}

    # 1. Validation type.
    payment_type = (data.get("type") or "").strip()
    if payment_type not in _CASH_IN_ALLOWED_TYPES:
        return Response(
            {
                "detail": (
                    f"Type {payment_type!r} non autorise pour saisie agence. "
                    f"Autorises : {sorted(_CASH_IN_ALLOWED_TYPES)}."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Montant strict > 0.
    try:
        montant = Decimal(str(data.get("montant") or "0"))
    except (TypeError, InvalidOperation):
        return Response(
            {"detail": "Montant invalide."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if montant <= 0:
        return Response(
            {"detail": "Le montant doit etre strictement positif."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 3. Resolve member.
    try:
        member_id = int(data.get("member_id"))
    except (TypeError, ValueError):
        return Response(
            {"detail": "member_id requis."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        member = Member.objects.get(pk=member_id)
    except Member.DoesNotExist:
        return Response(
            {"detail": "Membre introuvable."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # 4. Specifiques par type.
    loan = None
    nb_jours_couverts = 1
    is_placement = False
    if payment_type == Payment.Type.REMBOURSEMENT:
        from apps_coop.loans.models import Loan
        try:
            loan_id = int(data.get("loan_id"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "loan_id requis pour un REMBOURSEMENT."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            loan = Loan.objects.get(pk=loan_id, member=member)
        except Loan.DoesNotExist:
            return Response(
                {
                    "detail": (
                        f"Credit #{loan_id} introuvable ou pas du membre."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
    elif payment_type == Payment.Type.EPARGNE:
        try:
            nb_jours_couverts = int(data.get("nb_jours_couverts") or 1)
        except (TypeError, ValueError):
            nb_jours_couverts = 1
        if nb_jours_couverts < 1:
            return Response(
                {"detail": "nb_jours_couverts doit etre >= 1."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif payment_type == Payment.Type.EPARGNE_CLASSIQUE:
        is_placement = bool(data.get("is_placement", False))

    reference_externe = (data.get("reference_externe") or "").strip()[:64]
    note = (data.get("note") or "").strip()[:500]
    # D6 . Flag explicite is_renewal pour FRAIS_CARNET . declenche
    # apply_membership_renewal au lieu de creer un nouveau BookletOrder.
    is_renewal_flag = bool(data.get("is_renewal", False))
    now = timezone.now()

    # 5. Creation Payment + execution hook . tout dans une transaction pour
    # qu'un echec du hook annule la creation Payment.
    with db_transaction.atomic():
        payment = Payment.objects.create(
            member=member,
            montant=montant,
            type=payment_type,
            source=Payment.Source.MANUEL,
            statut=Payment.Statut.VALIDE,
            loan=loan,
            validated_by=request.user,
            date_versement=now,
            date_validation=now,
            reference_externe=reference_externe,
            nb_jours_couverts=nb_jours_couverts,
            is_placement=is_placement,
        )
        # Execution du hook business . meme code que webhook Tara.
        from .services import _BUSINESS_HOOKS

        handler = _BUSINESS_HOOKS.get(payment.type)
        if handler is not None:
            handler(
                payment,
                {
                    "cash_in_admin": True,
                    "note": note,
                    # D6 . Propage le flag is_renewal au hook _hook_carnet_fees
                    # qui detecte le renouvellement annuel via raw["is_renewal"].
                    "is_renewal": is_renewal_flag,
                },
            )

    # Audit (post-commit cote securite, mais lecture seule, ne casse pas le flow).
    record_audit(
        action="payment.cash_in_admin",
        entite_type="Payment",
        entite_id=payment.id,
        user=request.user,
        details={
            "type": payment.type,
            "montant": str(payment.montant),
            "member_id": member.id,
            "numero_membre": member.numero_membre,
            "loan_id": loan.id if loan else None,
            "reference_externe": reference_externe,
            "note": note,
            "is_placement": is_placement,
            "nb_jours_couverts": nb_jours_couverts,
        },
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )

    # Notif in-app au membre (re-utilise la fonction existante).
    try:
        from .services import _notify_payment_confirmed
        _notify_payment_confirmed(payment)
    except Exception:  # noqa: BLE001
        logger.warning("cash_in . notif in-app a echoue", exc_info=True)

    return Response(
        PaymentReadSerializer(payment).data,
        status=status.HTTP_201_CREATED,
    )
