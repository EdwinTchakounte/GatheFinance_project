"""Savings API views — portal-side read endpoints.

Deposits and withdrawals don't go through this app: they flow through
``/api/v1/payments/init/`` (cf. ``apps_coop.payments``) and the
``_hook_savings_deposit`` hook applies the side-effects when the webhook
arrives. This view is consumption-only.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.permissions import IsActiveMember, IsMember, IsStaff

from .cutoff import COLLECTION_LOCATION, DAILY_CUTOFF_HOUR
from .models import ClassicSavingsAccount, SavingsAccount, SavingsTransaction
from .serializers import SavingsAccountReadSerializer, SavingsTransactionReadSerializer


class _TxPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema(
    tags=["savings"],
    summary="Compte d'épargne du membre connecté",
    description=(
        "Renvoie le solde, le taux d'intérêt annuel appliqué et les 10 dernières "
        "transactions du `SavingsAccount` du membre. Réservé aux membres actifs "
        "ou suspendus (lecture seule)."
    ),
)
class SavingsAccountMeView(generics.RetrieveAPIView):
    """GET /api/v1/savings/me/

    Returns the authenticated member's savings account snapshot:
    balance, interest rate, and the 10 most recent transactions.
    """

    permission_classes = [IsMember]
    serializer_class = SavingsAccountReadSerializer

    def get_object(self) -> SavingsAccount:
        member = self.request.user.member
        try:
            return member.savings_account
        except SavingsAccount.DoesNotExist as exc:
            # Should never happen — created at adhesion approval — but stay defensive.
            raise NotFound("Compte d'épargne introuvable. Contacte la coopérative.") from exc


@extend_schema(
    tags=["savings"],
    summary="Historique paginé des transactions d'épargne",
    description=(
        "Liste paginée (20/page) de toutes les transactions du membre, les plus "
        "récentes d'abord. Filtre optionnel `?type_op=depot|retrait|interet`. "
        "Réservé au membre connecté."
    ),
)
class SavingsTransactionListView(generics.ListAPIView):
    """GET /api/v1/savings/transactions/?page=&type_op="""

    permission_classes = [IsMember]
    serializer_class = SavingsTransactionReadSerializer
    pagination_class = _TxPagination

    def get_queryset(self):
        try:
            account = self.request.user.member.savings_account
        except SavingsAccount.DoesNotExist as exc:
            raise NotFound("Compte d'épargne introuvable.") from exc
        qs = SavingsTransaction.objects.filter(account=account).order_by("-date", "-id")
        type_op = self.request.query_params.get("type_op")
        if type_op:
            qs = qs.filter(type_op=type_op)
        return qs


@extend_schema(
    tags=["savings"],
    summary="Règles publiques de la collecte (canaux, cut-off, taux)",
    description=(
        "Renvoie les paramètres réglementaires affichés aux membres et "
        "aux visiteurs : montant journalier suggéré, heure limite, "
        "canaux disponibles (app + agence), taux de rémunération mensuel. "
        "Endpoint public (pas d'authentification)."
    ),
)
class SavingsInfoView(APIView):
    """GET /api/v1/savings/info/ — règlement public (Article 4 amendé).

    Article 4 (amendé) : le membre verse sa cotisation soit via l'application
    mobile (Mobile Money — canal principal), soit à l'agence (canal de
    secours). Le montant 1 000 FCFA est suggéré mais le membre est libre de
    verser un montant différent.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get(self, request):
        # Taux et frais lus en base (modifiables côté admin, BR2) avec fallback
        # réglementaire.
        from apps_coop.audit.services import get_int_setting, get_str_setting
        from apps_coop.payments.models import FeeType, RateParam
        from apps_coop.payments.rates import get_rate

        taux_mensuel = get_rate(RateParam.Code.SAVINGS_INTEREST_MONTHLY)
        carnet = (
            FeeType.objects.filter(code=FeeType.Code.CARNET, actif=True)
            .values_list("montant", flat=True)
            .first()
        )

        # LOT 6 (refonte 2026) — paramètres collecte / multi-jours pré-payé.
        min_per_day = get_int_setting("collecte.min_per_day", 1000)
        prepay_max_days = get_int_setting("collecte.prepay.max_days", 30)
        commission_rate = get_str_setting("collecte.monthly.commission_rate", "0.01")
        end_of_month_default = get_str_setting("collecte.monthly.default_action", "cash")

        return Response(
            {
                "suggested_daily_amount_xaf": min_per_day,
                "min_amount_xaf": 100,
                "cutoff_hour": DAILY_CUTOFF_HOUR,
                "cutoff_label": f"{DAILY_CUTOFF_HOUR}h00",
                "cutoff_note": (
                    "Après 17h00 ou un week-end, le versement est porté en "
                    "date de valeur du jour ouvré suivant."
                ),
                "channels": [
                    {
                        "code": "mobile",
                        "label": "Application (Mobile Money via Tara)",
                        "primary": True,
                        "available_247": True,
                    },
                    {
                        "code": "agency",
                        "label": "Agence — Akwa Bercy",
                        "primary": False,
                        "available_247": False,
                        "location": COLLECTION_LOCATION,
                        "hours": "Lun–Ven · 08h00 – 17h00",
                    },
                ],
                "interest_rate_monthly": str(taux_mensuel),  # LEGACY 2025 — neutralisé en 2026
                "booklet_fee_xaf": int(carnet) if carnet is not None else 1000,
                # Refonte 2026 — collecte journalière.
                "collecte_min_per_day_xaf": min_per_day,
                "collecte_prepay_max_days": prepay_max_days,
                "collecte_monthly_commission_rate": commission_rate,
                "collecte_end_of_month_default": end_of_month_default,
            }
        )


# ── Épargne classique (dissociée de la cotisation) ──────────────────────────

@extend_schema(
    tags=["savings"],
    summary="Compte épargne classique du membre + config",
    description=(
        "Renvoie le solde, les 10 dernières transactions et la configuration "
        "du produit épargne classique (taux, bornes de dépôt, ouverture). "
        "Le compte est créé à la volée s'il n'existe pas encore (solde 0)."
    ),
)
@api_view(["GET"])
@permission_classes([IsMember])
def classic_savings_me(request):
    from datetime import date

    from .models import ClassicSavingsAccount
    from .serializers import ClassicSavingsAccountReadSerializer

    member = request.user.member
    account, _ = ClassicSavingsAccount.objects.get_or_create(
        member=member,
        defaults={"date_ouverture": date.today()},
    )
    return Response(ClassicSavingsAccountReadSerializer(account).data)


@extend_schema(
    tags=["savings"],
    summary="Historique paginé des transactions d'épargne classique",
    description=(
        "Liste paginée (20/page) des transactions du compte épargne classique "
        "du membre, les plus récentes d'abord. Filtre optionnel "
        "`?type_op=depot|retrait|interet`. Miroir de "
        "`/savings/transactions/` (collecte) — permet de dissocier l'affichage "
        "des deux produits côté portail. Réservé au membre connecté."
    ),
)
class ClassicSavingsTransactionListView(generics.ListAPIView):
    """GET /api/v1/savings/classic/transactions/?page=&type_op="""

    permission_classes = [IsMember]
    pagination_class = _TxPagination

    def get_serializer_class(self):
        from .serializers import ClassicSavingsTransactionReadSerializer

        return ClassicSavingsTransactionReadSerializer

    def get_queryset(self):
        from datetime import date

        from .models import ClassicSavingsTransaction

        member = self.request.user.member
        account, _ = ClassicSavingsAccount.objects.get_or_create(
            member=member,
            defaults={"date_ouverture": date.today()},
        )
        qs = ClassicSavingsTransaction.objects.filter(account=account).order_by(
            "-date", "-id"
        )
        type_op = self.request.query_params.get("type_op")
        if type_op:
            qs = qs.filter(type_op=type_op)
        return qs


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — configuration de l'épargne classique",
    description="GET lit la config, PATCH la met à jour (staff). Singleton.",
)
@api_view(["GET", "PATCH"])
@permission_classes([IsStaff])
def classic_savings_config(request):
    from .models import ClassicSavingsConfig
    from .serializers import ClassicSavingsConfigSerializer

    cfg = ClassicSavingsConfig.get_solo()
    if request.method == "GET":
        return Response(ClassicSavingsConfigSerializer(cfg).data)

    s = ClassicSavingsConfigSerializer(cfg, data=request.data, partial=True)
    s.is_valid(raise_exception=True)
    s.save()
    record_audit(
        action="config.classic_savings_updated",
        entite_type="ClassicSavingsConfig",
        entite_id=cfg.pk,
        user=request.user,
        details={k: str(v) for k, v in s.validated_data.items()},
        ip=client_ip(request),
    )
    return Response(ClassicSavingsConfigSerializer(cfg).data)


# ── Retrait d'épargne ───────────────────────────────────────────────────────

@extend_schema(
    tags=["savings"],
    summary="Demander un retrait d'épargne",
    description=(
        "Le membre actif demande un retrait. Crée une `WithdrawalRequest` en "
        "attente de validation administrative. Refusé si montant > solde ou si "
        "une demande est déjà en attente."
    ),
)
@api_view(["POST"])
@permission_classes([IsActiveMember])
def request_withdrawal_view(request):
    from .serializers import (
        WithdrawalRequestCreateSerializer,
        WithdrawalRequestReadSerializer,
    )
    from .services import request_withdrawal

    s = WithdrawalRequestCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        account = request.user.member.savings_account
    except SavingsAccount.DoesNotExist:
        return Response({"detail": "Compte d'épargne introuvable."}, status=status.HTTP_404_NOT_FOUND)
    try:
        wr = request_withdrawal(
            account,
            montant=s.validated_data["montant"],
            motif=s.validated_data.get("motif", ""),
            mode_paiement=s.validated_data.get("mode_paiement"),
            recipient_phone=s.validated_data.get("recipient_phone", ""),
            network=s.validated_data.get("network", ""),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        WithdrawalRequestReadSerializer(wr).data,
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["savings"],
    summary="Mes demandes de retrait",
)
@api_view(["GET"])
@permission_classes([IsMember])
def my_withdrawals(request):
    from .models import WithdrawalRequest
    from .serializers import WithdrawalRequestReadSerializer

    try:
        account = request.user.member.savings_account
    except SavingsAccount.DoesNotExist:
        return Response({"results": []})
    qs = WithdrawalRequest.objects.filter(account=account).order_by("-date_demande")
    return Response({"results": WithdrawalRequestReadSerializer(qs, many=True).data})


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — liste des demandes de retrait",
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_withdrawals(request):
    from .models import WithdrawalRequest
    from .serializers import WithdrawalRequestReadSerializer

    qs = WithdrawalRequest.objects.select_related("account", "account__member").order_by(
        "-date_demande"
    )
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    data = []
    for wr in qs[:200]:
        row = WithdrawalRequestReadSerializer(wr).data
        row["numero_membre"] = wr.account.member.numero_membre
        row["member_nom"] = f"{wr.account.member.prenom} {wr.account.member.nom}".strip()
        # Hint UI for action buttons
        row["can_mark_paid"] = (
            wr.mode_paiement == WithdrawalRequest.ModePaiement.PRESENTIEL
            and wr.statut == WithdrawalRequest.Statut.APPROUVEE
        )
        row["can_retry_payout"] = (
            wr.mode_paiement == WithdrawalRequest.ModePaiement.MOMO
            and wr.statut == WithdrawalRequest.Statut.PAYOUT_FAILED
        )
        data.append(row)
    return Response({"results": data})


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — décider d'une demande de retrait",
    description=(
        "Approuve ou rejette une demande de retrait.\n\n"
        "**À l'approbation** : le solde est débité, puis selon le canal choisi "
        "par le membre :\n"
        "  • `mode_paiement = momo` → init payout Tara automatique. Statut "
        "passe à `en_payout` puis `completee` après confirmation webhook (ou "
        "`payout_failed` si Tara KO).\n"
        "  • `mode_paiement = presentiel` → statut `approuvee` (attente de "
        "remise espèces). L'admin appellera ensuite `/mark-paid/` pour clôturer."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_decide_withdrawal(request, pk: int):
    from .models import WithdrawalRequest
    from .serializers import WithdrawalDecideSerializer, WithdrawalRequestReadSerializer
    from .services import decide_withdrawal

    s = WithdrawalDecideSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        wr = WithdrawalRequest.objects.get(pk=pk)
    except WithdrawalRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
    try:
        wr = decide_withdrawal(
            wr,
            decided_by=request.user,
            approve=s.validated_data["decision"] == "approuvee",
            motif_rejet=s.validated_data.get("motif_rejet", ""),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WithdrawalRequestReadSerializer(wr).data)


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — confirmer remise espèces (retrait présentiel)",
    description=(
        "Marque un retrait `approuvee` en `completee` après remise effective "
        "des espèces au membre. Réservé aux retraits `mode_paiement = presentiel`. "
        "Idempotent : un retrait déjà `completee` renvoie 200."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_mark_withdrawal_paid(request, pk: int):
    from .models import WithdrawalRequest
    from .serializers import WithdrawalHandoverSerializer, WithdrawalRequestReadSerializer
    from .services import mark_withdrawal_paid

    s = WithdrawalHandoverSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    try:
        wr = WithdrawalRequest.objects.get(pk=pk)
    except WithdrawalRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
    try:
        wr = mark_withdrawal_paid(
            wr, agent=request.user, note=s.validated_data.get("note", ""),
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WithdrawalRequestReadSerializer(wr).data)


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — réessayer un payout MOMO échoué",
    description=(
        "Relance un init payout Tara pour un retrait `payout_failed`. "
        "Réutilise la même WithdrawalRequest (solde déjà débité), nouveau "
        "Payment + nouvelle idempotency_key côté Tara."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_retry_withdrawal_payout(request, pk: int):
    from .models import WithdrawalRequest
    from .serializers import WithdrawalRequestReadSerializer
    from .services import retry_withdrawal_payout

    try:
        wr = WithdrawalRequest.objects.get(pk=pk)
    except WithdrawalRequest.DoesNotExist:
        return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
    try:
        wr = retry_withdrawal_payout(wr, agent=request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(WithdrawalRequestReadSerializer(wr).data)


# ===========================================================================
# LOT 7-admin (refonte 2026) — Renouvellements épargne classique
# ===========================================================================


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — liste des comptes épargne en attente de renouvellement",
    description=(
        "Renvoie les ClassicSavingsAccount dont le statut de renouvellement "
        "nécessite une action de la coop. Filtre par défaut : "
        "``en_attente_paiement`` (maturité atteinte). "
        "Filtres : ``?statut=actif|notifie|urgence|en_attente_paiement|archive``."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_renewals(request):
    statut = request.query_params.get("statut", "en_attente_paiement")
    qs = (
        ClassicSavingsAccount.objects
        .select_related("member", "member__user")
        .filter(statut_renouvellement=statut)
        .order_by("date_prochaine_maturite")
    )
    rows = [
        {
            "id": acc.id,
            "member_id": acc.member_id,
            "member_numero": acc.member.numero_membre,
            "member_nom": acc.member.nom,
            "member_prenom": acc.member.prenom,
            "member_email": getattr(acc.member.user, "email", "") or "",
            "solde": str(acc.solde),
            "cycle_courant": acc.cycle_courant,
            "date_ouverture": acc.date_ouverture.isoformat(),
            "date_prochaine_maturite": (
                acc.date_prochaine_maturite.isoformat()
                if acc.date_prochaine_maturite else None
            ),
            "statut_renouvellement": acc.statut_renouvellement,
            "statut_display": acc.get_statut_renouvellement_display(),
        }
        for acc in qs[:200]
    ]
    return Response({"count": len(rows), "results": rows})


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — encaisser les frais et renouveler un compte épargne",
    description=(
        "Acte le renouvellement annuel : avance ``cycle_courant``, pose une "
        "nouvelle ``date_prochaine_maturite``, écrit la ligne FRAIS_RENOUVELLEMENT "
        "dans le ledger et restaure ``statut_renouvellement = ACTIF``. "
        "Refusé si le compte est ARCHIVE."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_process_renewal(request, pk: int):
    from .services import renew_classic_savings_account

    try:
        account = ClassicSavingsAccount.objects.get(pk=pk)
    except ClassicSavingsAccount.DoesNotExist:
        return Response(
            {"detail": "Compte introuvable."}, status=status.HTTP_404_NOT_FOUND
        )
    paid_amount_raw = request.data.get("paid_amount")
    try:
        paid_amount = None if paid_amount_raw is None else paid_amount_raw
        account = renew_classic_savings_account(
            account=account,
            paid_by=request.user,
            paid_amount=paid_amount,
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(
        {
            "id": account.id,
            "cycle_courant": account.cycle_courant,
            "statut_renouvellement": account.statut_renouvellement,
            "date_prochaine_maturite": (
                account.date_prochaine_maturite.isoformat()
                if account.date_prochaine_maturite else None
            ),
        }
    )


# ---------------------------------------------------------------------------
# Cron intérêts épargne — déclenchement manuel admin (recette)
# ---------------------------------------------------------------------------


@extend_schema(
    tags=["admin"],
    summary="Déclencher le crédit d'intérêts mensuel pour une période",
    description=(
        "Joue ``crediter_interets_mensuels`` pour le mois ciblé. Bypass le "
        "kill-switch ``savings.monthly_interest.enabled`` (force=true). "
        "Body : ``{period: 'YYYY-MM'}`` (défaut = mois courant). "
        "Émet les notifications normalement (l'admin valide ainsi le flow "
        "intérêts + email). Idempotent : ne crédite pas 2× le même mois."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_run_monthly_interest(request):
    from datetime import datetime

    from django.utils import timezone as dj_tz

    from .tasks import crediter_interets_mensuels

    period_raw = (request.data.get("period") or "").strip()
    target = None
    if period_raw:
        try:
            year_s, month_s = period_raw.split("-")
            target = datetime(int(year_s), int(month_s), 1, tzinfo=dj_tz.get_current_timezone())
        except (ValueError, AttributeError):
            return Response(
                {"detail": "period doit être au format YYYY-MM (ex. 2026-05)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    summary = crediter_interets_mensuels(target_month=target, force=True)
    record_audit(
        action="admin.savings_interest.manual_run",
        entite_type="cron",
        user=request.user,
        details={"period": summary.get("period"), "summary": summary},
        ip=client_ip(request),
    )
    return Response(summary)
