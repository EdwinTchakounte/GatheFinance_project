"""Savings API views — portal-side read endpoints.

Deposits and withdrawals don't go through this app: they flow through
``/api/v1/payments/init/`` (cf. ``apps_coop.payments``) and the
``_hook_savings_deposit`` hook applies the side-effects when the webhook
arrives. This view is consumption-only.
"""
from __future__ import annotations

from decimal import Decimal

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
from .models import SavingsAccount, SavingsTransaction
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
        return Response(
            {
                "suggested_daily_amount_xaf": 1000,
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
                "interest_rate_monthly": "0.01",  # 1 % / mois (Article 4)
                "booklet_fee_xaf": 1000,
            }
        )


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
        data.append(row)
    return Response({"results": data})


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — décider d'une demande de retrait",
    description="Approuve (débite le solde) ou rejette une demande de retrait.",
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
