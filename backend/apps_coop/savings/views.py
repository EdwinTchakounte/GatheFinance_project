"""Savings API views — portal-side read endpoints.

Deposits and withdrawals don't go through this app: they flow through
``/api/v1/payments/init/`` (cf. ``apps_coop.payments``) and the
``_hook_savings_deposit`` hook applies the side-effects when the webhook
arrives. This view is consumption-only.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps_coop.audit.services import client_ip, record as record_audit
from apps_coop.members.naming import full_name
from apps_coop.members.permissions import IsActiveMember, IsAdmin, IsMember, IsStaff

from .cutoff import COLLECTION_LOCATION, DAILY_CUTOFF_HOUR
from .models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)
from .serializers import SavingsAccountReadSerializer, SavingsTransactionReadSerializer


class _TxPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _apply_booklet_filter(qs, request):
    """Filtre l'historique d'écritures PAR CARNET : ``?booklet_order=<id>``
    (un carnet précis) et/ou ``?booklet_annee=<AAAA>`` (tous les carnets d'une
    année). Sans paramètre, renvoie tout. Maintenant que chaque écriture porte
    son carnet, ce filtre donne « toutes les écritures d'un carnet donné »."""
    booklet_id = (request.query_params.get("booklet_order") or "").strip()
    if booklet_id.isdigit():
        qs = qs.filter(booklet_order_id=int(booklet_id))
    annee = (request.query_params.get("booklet_annee") or "").strip()
    if annee.isdigit():
        qs = qs.filter(booklet_order__annee=int(annee))
    return qs


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
        return _apply_booklet_filter(qs, self.request)


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
        amount_step = get_int_setting("collecte.amount_step", 50)
        commission_rate = get_str_setting("collecte.monthly.commission_rate", "0.01")
        end_of_month_default = get_str_setting("collecte.monthly.default_action", "cash")

        return Response(
            {
                "suggested_daily_amount_xaf": min_per_day,
                # Minimum réel = le minimum par jour de collecte (et non 100, qui
                # était trompeur : l'enforcement backend utilise min_per_day).
                "min_amount_xaf": min_per_day,
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
                "collecte_amount_step_xaf": amount_step,
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
        return _apply_booklet_filter(qs, self.request)


@extend_schema(
    tags=["savings"],
    summary="États par carnet du membre connecté",
    description=(
        "Pour chaque carnet ayant des écritures : nb d'écritures, total "
        "crédité, total débité et net du carnet (crédits − débits). Sert la "
        "vue « Mes carnets » (groupée par carnet). Épargne collecte + classique."
    ),
)
@api_view(["GET"])
@permission_classes([IsMember])
def booklet_summaries_me(request):
    from .booklet_summary import member_booklet_summaries

    return Response({"results": member_booklet_summaries(request.user.member)})


@extend_schema(
    tags=["savings"],
    summary="🔒 Admin — états par carnet d'un membre",
    description="Même agrégation que la vue membre, pour un membre donné (staff).",
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_member_booklet_summaries(request, pk: int):
    from apps_coop.members.models import Member

    from .booklet_summary import member_booklet_summaries

    try:
        member = Member.objects.get(pk=pk)
    except Member.DoesNotExist:
        return Response({"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"results": member_booklet_summaries(member)})


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


# ── Collecte : choix de fin de mois (cash vs bascule épargne) ───────────────

@extend_schema(
    tags=["savings"],
    summary="Choix de fin de mois du membre (collecte)",
    description=(
        "GET : renvoie le choix courant. POST {preference: 'cash'|'epargne'} : "
        "le membre décide, pour la prochaine clôture mensuelle, de récupérer sa "
        "collecte en cash (après commission 1%) ou de la basculer vers son "
        "épargne classique."
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsActiveMember])
def collecte_end_of_month_preference(request):
    account = request.user.member.savings_account
    if request.method == "GET":
        return Response(
            {
                "preference": account.end_of_month_preference,
                "payout_phone": account.payout_phone,
                "payout_network": account.payout_network,
            }
        )

    pref = (request.data.get("preference") or "").strip()
    valid = {c for c, _ in SavingsAccount.EndOfMonthPreference.choices}
    if pref not in valid:
        return Response(
            {"detail": "preference doit valoir 'cash', 'mobile_money' ou 'epargne'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    update_fields = ["end_of_month_preference"]
    account.end_of_month_preference = pref

    # Choix « versement Mobile Money » : le membre renseigne sa destination.
    if pref == SavingsAccount.EndOfMonthPreference.MOBILE_MONEY:
        from apps_coop.savings.models import WithdrawalRequest

        phone = (request.data.get("payout_phone") or "").strip()
        network = (request.data.get("payout_network") or "").strip().upper()
        if not phone:
            return Response(
                {"detail": "Le numéro Mobile Money de destination est requis."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if network and network not in WithdrawalRequest.Network.values:
            return Response(
                {"detail": f"Réseau Mobile Money invalide : {network!r}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        account.payout_phone = phone
        account.payout_network = network
        update_fields += ["payout_phone", "payout_network"]

    account.save(update_fields=update_fields)
    record_audit(
        action="collecte.end_of_month_preference.set",
        entite_type="SavingsAccount",
        entite_id=account.pk,
        user=request.user,
        details={"preference": pref},
        ip=client_ip(request),
    )
    return Response(
        {
            "preference": account.end_of_month_preference,
            "payout_phone": account.payout_phone,
            "payout_network": account.payout_network,
        }
    )


@extend_schema(
    tags=["savings"],
    summary="Admin — choix de fin de mois des membres (collecte)",
    description=(
        "Vue de pilotage : pour chaque membre ayant un solde de collecte, son "
        "choix de fin de mois (cash / bascule épargne) et son solde courant. "
        "Sert l'onglet admin « Fin de mois collecte »."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_collecte_preferences(request):
    only_active = (request.query_params.get("only_active") or "").lower() in (
        "1", "true", "yes",
    )
    qs = (
        SavingsAccount.objects.select_related("member")
        .order_by("-solde", "member__numero_membre")
    )
    if only_active:
        qs = qs.filter(solde__gt=0)
    results = [
        {
            "member_id": a.member_id,
            "numero_membre": a.member.numero_membre,
            "nom": a.member.nom_complet,
            "solde": str(a.solde),
            "preference": a.end_of_month_preference,
            # Destination du versement MoMo (préférence mobile_money) : sans
            # elle, l'admin ne peut pas exécuter le « versement sur mon compte ».
            "payout_phone": a.payout_phone,
            "payout_network": a.payout_network,
        }
        for a in qs
    ]
    # Compteurs récap pour l'en-tête de l'onglet.
    summary = {
        "cash": sum(1 for r in results if r["preference"] == "cash"),
        "mobile_money": sum(
            1 for r in results if r["preference"] == "mobile_money"
        ),
        "epargne": sum(1 for r in results if r["preference"] == "epargne"),
        "total": len(results),
    }
    return Response({"summary": summary, "results": results})


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

    from .models import ClassicSavingsAccount, WithdrawalRequest

    s = WithdrawalRequestCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    member = request.user.member
    source = s.validated_data.get("source", WithdrawalRequest.Source.COLLECTE)

    account = None
    classic_account = None
    if source == WithdrawalRequest.Source.CLASSIQUE_LIBRE:
        try:
            classic_account = member.classic_savings_account
        except ClassicSavingsAccount.DoesNotExist:
            return Response(
                {"detail": "Compte épargne classique introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        try:
            account = member.savings_account
        except SavingsAccount.DoesNotExist:
            return Response(
                {"detail": "Compte de collecte introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )
    try:
        wr = request_withdrawal(
            account,
            montant=s.validated_data["montant"],
            motif=s.validated_data.get("motif", ""),
            mode_paiement=s.validated_data.get("mode_paiement"),
            recipient_phone=s.validated_data.get("recipient_phone", ""),
            network=s.validated_data.get("network", ""),
            source=source,
            classic_account=classic_account,
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
    from django.db.models import Q

    from .models import WithdrawalRequest
    from .serializers import WithdrawalRequestReadSerializer

    member = request.user.member
    # Retraits collecte (account) ET classique (classic_account), tous produits.
    qs = (
        WithdrawalRequest.objects.filter(
            Q(account__member=member) | Q(classic_account__member=member)
        )
        .order_by("-date_demande")
    )
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

    from django.db.models import Q

    from apps_coop.members.models import Member

    qs = (
        WithdrawalRequest.objects.select_related(
            "account", "account__member", "classic_account", "classic_account__member"
        )
        # Masque les retraits des membres radiés (« supprimés »).
        .exclude(
            Q(account__member__statut=Member.Statut.RADIE)
            | Q(classic_account__member__statut=Member.Statut.RADIE)
        )
        .order_by("-date_demande")
    )
    statut = request.query_params.get("statut")
    if statut:
        qs = qs.filter(statut=statut)
    data = []
    for wr in qs[:200]:
        member = wr.member
        row = WithdrawalRequestReadSerializer(wr).data
        row["member_id"] = member.id
        row["numero_membre"] = member.numero_membre
        row["member_nom"] = full_name(member.prenom, member.nom)
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


# ── Écritures antidatées — reprise d'historique des carnets papier ───────────

@extend_schema(
    tags=["savings"],
    summary="🔒 Staff — créer un carnet antidaté (reprise carnet papier)",
    description=(
        "Crée un `BookletOrder` daté dans le passé, pour un membre dont le "
        "carnet papier existe déjà. Marqué DELIVREE. Ne rejoue aucun hook (pas "
        "de renouvellement d'adhésion, pas de second carnet). Les écritures "
        "antidatées postérieures s'y rattacheront.\n\n"
        "Body : `member_id`, `date` (ISO, passée), `montant` (optionnel, défaut "
        "0 — le carnet existe déjà, pas de ré-encaissement), `annee` "
        "(optionnel), `note` (optionnel)."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_create_antidated_booklet(request):
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation

    from apps_coop.members.models import Member

    from .antidated_services import (
        AntidatedEntryError,
        create_antidated_booklet,
    )

    data = request.data
    try:
        member = Member.objects.get(pk=data.get("member_id"))
    except (Member.DoesNotExist, TypeError, ValueError):
        return Response(
            {"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND
        )

    raw_date = (data.get("date") or "").strip()
    try:
        date_op = _date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return Response(
            {"detail": "Date invalide (attendu AAAA-MM-JJ)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        montant = Decimal(str(data.get("montant") or "0"))
    except (InvalidOperation, TypeError):
        return Response(
            {"detail": "Montant invalide."}, status=status.HTTP_400_BAD_REQUEST
        )

    annee = data.get("annee")
    try:
        annee = int(annee) if annee not in (None, "") else None
    except (TypeError, ValueError):
        return Response(
            {"detail": "Année invalide."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = create_antidated_booklet(
            member=member,
            date_op=date_op,
            montant=montant,
            annee=annee,
            note=str(data.get("note") or ""),
            recorded_by=request.user,
        )
    except AntidatedEntryError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "booklet_order_id": result.booklet_order_id,
            "payment_id": result.payment_id,
            "date": result.date.date().isoformat(),
            "annee": result.annee,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["savings"],
    summary="🔒 Staff — enregistrer une écriture antidatée (reprise carnet papier)",
    description=(
        "Ressaisit une écriture (versement OU retrait) d'un carnet papier à sa "
        "**vraie date**, pour les deux produits (collecte journalière ou épargne "
        "classique). Reprise d'historique seule : AUCUNE clôture rejouée, aucun "
        "Payment, aucune notification. Le solde du compte est ajusté et la ligne "
        "de grand livre pointe vers le carnet actif à cette date.\n\n"
        "Body : `member_id`, `product` (`collecte`|`classique`), `sens` "
        "(`depot`|`retrait`), `montant`, `date` (ISO, passée), `booklet_order_id` "
        "(optionnel), `note` (optionnel). 409 si le retrait rendrait le solde "
        "négatif (ressaisir les dépôts avant les retraits)."
    ),
)
@api_view(["POST"])
@permission_classes([IsStaff])
def admin_record_antidated_entry(request):
    from datetime import date as _date
    from decimal import Decimal, InvalidOperation

    from apps_coop.members.models import BookletOrder, Member

    from .antidated_services import (
        AntidatedEntryError,
        record_antidated_entry,
    )

    data = request.data
    try:
        member = Member.objects.get(pk=data.get("member_id"))
    except (Member.DoesNotExist, TypeError, ValueError):
        return Response(
            {"detail": "Membre introuvable."}, status=status.HTTP_404_NOT_FOUND
        )

    try:
        montant = Decimal(str(data.get("montant") or "0"))
    except (InvalidOperation, TypeError):
        return Response(
            {"detail": "Montant invalide."}, status=status.HTTP_400_BAD_REQUEST
        )

    raw_date = (data.get("date") or "").strip()
    try:
        date_op = _date.fromisoformat(raw_date)
    except (ValueError, TypeError):
        return Response(
            {"detail": "Date invalide (attendu AAAA-MM-JJ)."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    booklet = None
    booklet_id = data.get("booklet_order_id")
    if booklet_id:
        try:
            booklet = BookletOrder.objects.get(pk=booklet_id, member=member)
        except BookletOrder.DoesNotExist:
            return Response(
                {"detail": "Carnet introuvable pour ce membre."},
                status=status.HTTP_404_NOT_FOUND,
            )

    try:
        result = record_antidated_entry(
            member=member,
            product=str(data.get("product") or ""),
            sens=str(data.get("sens") or ""),
            montant=montant,
            date_op=date_op,
            booklet_order=booklet,
            cycle_id=data.get("cycle_id"),
            note=str(data.get("note") or ""),
            recorded_by=request.user,
        )
    except AntidatedEntryError as exc:
        # Toute incohérence de saisie = 400. (Le solde négatif n'est plus une
        # erreur : reprise d'historique, cf. record_antidated_entry.)
        return Response(
            {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
        )

    return Response(
        {
            "transaction_id": result.transaction_id,
            "product": result.product,
            "sens": result.sens,
            "montant": str(result.montant),
            "date": result.date.date().isoformat(),
            "solde_apres": str(result.solde_apres),
            "booklet_order_id": result.booklet_order_id,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["savings"],
    summary="Membre — relevé PDF de toutes les écritures de son carnet",
    description=(
        "PDF paginé listant TOUTES les écritures d'épargne du membre courant "
        "(collecte + classique), triées par date, avec le carnet de rattachement. "
        "Téléchargeable depuis l'onglet Carnet du mobile / portail."
    ),
    responses={200: OpenApiResponse(description="PDF binaire (application/pdf)")},
)
@api_view(["GET"])
@permission_classes([IsActiveMember])
def my_booklet_ledger_pdf(request):
    from django.http import HttpResponse

    from apps_coop.members.report_pdf import build_member_ledger_pdf

    member = request.user.member
    pdf = build_member_ledger_pdf(member)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = (
        f'inline; filename="gathe-ecritures-{member.numero_membre}.pdf"'
    )
    return resp


# --------------------------------------------------------------------------- #
# Onglet « Saisies antidatées » (admin) : historique + invalidation.
# --------------------------------------------------------------------------- #

def _antidated_row_dto(row, entite_type, product, member, sens):
    """Normalise une écriture antidatée (3 modèles) en dict pour le dashboard."""
    booklet = row.booklet_order
    return {
        "entite_type": entite_type,
        "id": row.id,
        "product": product,
        "sens": sens,
        "montant": str(row.montant),
        "solde_apres": str(row.solde_apres),
        "date": row.date.date().isoformat(),  # date métier (antidatée)
        "saisi_le": row.created_at.isoformat(),  # date de saisie réelle
        "membre": {
            "id": member.id,
            "numero": member.numero_membre,
            "nom": full_name(member.prenom, member.nom),
        },
        "booklet": (
            {"id": booklet.id, "annee": getattr(booklet, "annee", None),
             "type": getattr(booklet, "type", None)}
            if booklet else None
        ),
        "reversed": row.reversed_at is not None,
        "reversed_at": row.reversed_at.isoformat() if row.reversed_at else None,
        "reversal_note": row.reversal_note or "",
    }


@extend_schema(
    tags=["savings"],
    summary="Admin — historique des saisies antidatées (3 produits)",
    description=(
        "Liste UNIQUEMENT les écritures antidatées (flag `is_antidated`), tous "
        "produits confondus (collecte, classique, tontine/caisse), triées par "
        "date métier décroissante. Filtres : `?member_id`, `?product` "
        "(`collecte`|`classique`|`special`), `?include_reversed` (défaut 1). "
        "Pagination `?limit`/`?offset`."
    ),
)
@api_view(["GET"])
@permission_classes([IsStaff])
def admin_list_antidated_entries(request):
    from apps_coop.common import parse_pagination
    from apps_coop.special_collections.models import SpecialCollectionTransaction

    qp = request.query_params
    member_id = qp.get("member_id")
    product = (qp.get("product") or "").strip()
    include_reversed = (qp.get("include_reversed") or "1") not in ("0", "false", "no")

    T_COL = SavingsTransaction.TypeOp
    T_CLA = ClassicSavingsTransaction.TypeOp
    T_SPE = SpecialCollectionTransaction.TypeOp

    rows: list[dict] = []

    if product in ("", "collecte"):
        qs = (
            SavingsTransaction.objects.filter(is_antidated=True)
            .select_related("account__member", "booklet_order")
        )
        if member_id:
            qs = qs.filter(account__member_id=member_id)
        if not include_reversed:
            qs = qs.filter(reversed_at__isnull=True)
        for r in qs:
            sens = "depot" if r.type_op in {T_COL.DEPOT, T_COL.INTERET} else "retrait"
            rows.append(
                _antidated_row_dto(r, "SavingsTransaction", "collecte",
                                   r.account.member, sens)
            )

    if product in ("", "classique"):
        credit = {T_CLA.DEPOT, T_CLA.INTERET, T_CLA.INTERET_PLACEMENT,
                  T_CLA.INTERET_PRETEUR, T_CLA.BASCULE_COLLECTE}
        qs = (
            ClassicSavingsTransaction.objects.filter(is_antidated=True)
            .select_related("account__member", "booklet_order")
        )
        if member_id:
            qs = qs.filter(account__member_id=member_id)
        if not include_reversed:
            qs = qs.filter(reversed_at__isnull=True)
        for r in qs:
            sens = "depot" if r.type_op in credit else "retrait"
            rows.append(
                _antidated_row_dto(r, "ClassicSavingsTransaction", "classique",
                                   r.account.member, sens)
            )

    if product in ("", "special"):
        qs = (
            SpecialCollectionTransaction.objects.filter(is_antidated=True)
            .select_related("membership__member", "membership__cycle", "booklet_order")
        )
        if member_id:
            qs = qs.filter(membership__member_id=member_id)
        if not include_reversed:
            qs = qs.filter(reversed_at__isnull=True)
        for r in qs:
            sens = "retrait" if r.type_op == T_SPE.RETRAIT else "depot"
            dto = _antidated_row_dto(r, "SpecialCollectionTransaction", "special",
                                     r.membership.member, sens)
            dto["collection_type"] = getattr(r.membership.cycle, "type", None)
            rows.append(dto)

    # Tri global par date métier décroissante puis id (stable).
    rows.sort(key=lambda d: (d["date"], d["id"]), reverse=True)
    total = len(rows)
    offset, limit = parse_pagination(request, default_limit=25, max_limit=200)
    page = rows[offset:offset + limit]

    return Response({"count": total, "results": page})


@extend_schema(
    tags=["savings"],
    summary="Admin — invalider (contre-passer) une saisie antidatée",
    description=(
        "Annule l'effet d'une écriture antidatée erronée : contre-passe le solde "
        "et marque l'écriture invalidée (barrée en historique). Réservé aux "
        "admins. Le solde résultant peut être négatif (reprise d'historique) — "
        "signalé par `went_negative`. Body : `entite_type` "
        "(`SavingsTransaction`|`ClassicSavingsTransaction`|"
        "`SpecialCollectionTransaction`), `entite_id`, `motif` (optionnel)."
    ),
)
@api_view(["POST"])
@permission_classes([IsAdmin])
def admin_invalidate_antidated_entry(request):
    from .antidated_services import (
        AntidatedEntryError,
        invalidate_antidated_entry,
    )

    data = request.data
    entite_type = str(data.get("entite_type") or "")
    entite_id = data.get("entite_id")
    try:
        entite_id = int(entite_id)
    except (TypeError, ValueError):
        return Response(
            {"detail": "entite_id invalide."}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        result = invalidate_antidated_entry(
            entite_type,
            entite_id,
            actor=request.user,
            motif=str(data.get("motif") or ""),
        )
    except AntidatedEntryError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {
            "entite_type": result.entite_type,
            "entite_id": result.entite_id,
            "reverse_tx_id": result.reverse_tx_id,
            "solde_apres": str(result.solde_apres),
            "went_negative": result.went_negative,
        },
        status=status.HTTP_200_OK,
    )
