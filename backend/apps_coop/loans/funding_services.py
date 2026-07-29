"""Services de funding par les épargneurs-prêteurs (refonte 2026 §7.3 / LOT 8).

État de l'art côté demande :
  1. ``request_funding(loan)`` cherche N prêteurs, crée 1 ``LoanFundingRequest``
     + N ``LenderConsentRequest`` (1 par prêteur), pose deadline=now+24h.
  2. ``respond_to_consent_request(consent, accept, motif)`` permet à un
     prêteur de répondre explicitement avant l'expiration.
  3. ``finalize_funding(funding_request)`` est appelé soit dès qu'aucun
     PENDING ne subsiste (tous accepted/refused), soit par le cron à
     l'expiration de la fenêtre. Crée les ``LenderAllocation``, passe les
     ``LenderTranche`` à ENGAGEE, posiitonne ``FUNDED``.
  4. Si refus : on tente une réallocation (nouvelle vague avec nouveaux
     prêteurs). Si impossible → ``EN_ATTENTE_FUNDING`` (intervention admin).

L'algorithme d'allocation est tunable via ``funding.allocation_strategy``
(``first_fit`` ou ``balanced``). La fenêtre est tunable via
``funding.window_hours`` (24h par défaut).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Iterable

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    get_str_setting,
    record as record_audit,
)
from apps_coop.members.models import Member
from apps_coop.savings.lender_services import active_lenders_with_capacity
from apps_coop.savings.models import LenderTranche

from .models import (
    LenderAllocation,
    LenderConsentRequest,
    Loan,
    LoanFundingRequest,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Erreurs métier
# ---------------------------------------------------------------------------


class FundingError(Exception):
    """Erreur générique du flow funding."""


class InsufficientCapacity(FundingError):
    """Pas assez de capacité totale chez les prêteurs disponibles."""

    def __init__(self, montant_cible: Decimal, capacite_totale: Decimal):
        self.montant_cible = montant_cible
        self.capacite_totale = capacite_totale
        super().__init__(
            f"Capacité prêteur insuffisante : besoin {montant_cible} XAF, "
            f"disponible {capacite_totale} XAF."
        )


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


def _window_hours() -> int:
    """Fenêtre d'acceptation tacite, en heures (tunable ``funding.window_hours``)."""
    return get_int_setting("funding.window_hours", 24)


def _allocation_strategy() -> str:
    """Stratégie active (tunable ``funding.allocation_strategy``)."""
    val = get_str_setting("funding.allocation_strategy", "first_fit")
    return val if val in ("first_fit", "balanced") else "first_fit"


# ---------------------------------------------------------------------------
# Allocation : sélection de prêteurs + construction de propositions
# ---------------------------------------------------------------------------


@dataclass
class _Proposal:
    """Proposition à un prêteur pour une vague de funding."""

    lender: Member
    montant: Decimal
    tranche: LenderTranche | None  # None en mode A (créée à la finalisation)


def _propositions_for_lender(
    lender: Member, *, remaining: Decimal
) -> list[_Proposal]:
    """Construit les propositions pour UN prêteur jusqu'à ``remaining`` XAF.

    Mode B (tranches explicites) : pioche les LenderTranche DISPONIBLE par
    ordre d'arrivée jusqu'à atteindre ``remaining``.

    Mode A (global) : crée 1 proposition unique virtuelle (tranche=None),
    montant = min(remaining, capacite_pretable(lender)).
    """
    consent = lender.lender_consent
    out: list[_Proposal] = []

    if consent.is_global:
        capacite = lender.capacite_pretable
        montant = min(remaining, capacite)
        if montant > 0:
            out.append(_Proposal(lender=lender, montant=montant, tranche=None))
        return out

    # Mode B — itère les tranches DISPONIBLE.
    tranches = LenderTranche.objects.filter(
        member=lender,
        statut=LenderTranche.Statut.DISPONIBLE,
    ).order_by("created_at")

    for t in tranches:
        if remaining <= 0:
            break
        montant = min(Decimal(t.montant), remaining)
        out.append(_Proposal(lender=lender, montant=montant, tranche=t))
        remaining -= montant
    return out


def _allocate(
    *,
    montant_cible: Decimal,
    candidates: Iterable[Member],
    strategy: str,
    excluded_lender_ids: set[int] | None = None,
) -> list[_Proposal]:
    """Renvoie la liste des propositions couvrant ``montant_cible``.

    Si la somme finale est inférieure au cible → liste partielle (caller
    décide d'échouer ou pas).

    ``excluded_lender_ids`` permet d'exclure des prêteurs (utile en
    réallocation : on évite de re-proposer aux mêmes qui ont refusé).
    """
    excluded = excluded_lender_ids or set()
    # Pré-filtre + tri selon stratégie.
    eligible = [m for m in candidates if m.pk not in excluded]
    if strategy == "balanced":
        # Tri par capacité croissante : on étale en commençant par les
        # plus petits, pour répartir le risque.
        eligible.sort(key=lambda m: m.capacite_pretable)
    else:  # first_fit
        eligible.sort(key=lambda m: m.capacite_pretable, reverse=True)

    remaining = Decimal(montant_cible)
    propositions: list[_Proposal] = []
    for lender in eligible:
        if remaining <= 0:
            break
        for prop in _propositions_for_lender(lender, remaining=remaining):
            propositions.append(prop)
            remaining -= prop.montant
    return propositions


# ---------------------------------------------------------------------------
# Service principal — request_funding
# ---------------------------------------------------------------------------


@transaction.atomic
def request_funding(loan: Loan, *, actor=None) -> LoanFundingRequest:
    """Crée la ``LoanFundingRequest`` + N ``LenderConsentRequest`` pour ce Loan.

    Idempotent : si une funding_request existe déjà, on la renvoie telle
    quelle (l'admin peut relancer manuellement via un re-trigger).
    """
    existing = LoanFundingRequest.objects.select_for_update().filter(loan=loan).first()
    if existing is not None:
        return existing

    # Le funding porte sur le NET réellement décaissé (montant_decaisse_net = 90 %
    # du nominal en mode « intérêt à la source »), PAS le brut nominal : les
    # intérêts retenus à la source ne sortent pas de la caisse, il n'y a donc rien
    # à financer dessus. Ex. crédit 60 000 dont 10 % coupés → funding sur 54 000.
    montant_cible = Decimal(loan.montant_decaisse_net or loan.montant)
    strategy = _allocation_strategy()
    candidates = list(active_lenders_with_capacity())

    propositions = _allocate(
        montant_cible=montant_cible,
        candidates=candidates,
        strategy=strategy,
    )

    total_alloue = sum((p.montant for p in propositions), Decimal("0"))
    now = timezone.now()
    deadline = now + timedelta(hours=_window_hours())

    fr = LoanFundingRequest.objects.create(
        loan=loan,
        montant_total=montant_cible,
        strategy=strategy,
        deadline=deadline,
    )

    if total_alloue < montant_cible:
        # Capacité insuffisante dès la 1re vague — on pose néanmoins les
        # propositions partielles puis on bascule EN_ATTENTE_FUNDING.
        for prop in propositions:
            LenderConsentRequest.objects.create(
                funding_request=fr,
                lender=prop.lender,
                tranche=prop.tranche,
                montant_propose=prop.montant,
                deadline=deadline,
            )
        fr.statut = LoanFundingRequest.Statut.EN_ATTENTE_FUNDING
        fr.save(update_fields=["statut", "updated_at"])
        record_audit(
            action="loan.funding.insufficient",
            entite_type="LoanFundingRequest",
            entite_id=fr.id,
            user=actor,
            details={
                "loan_id": loan.id,
                "montant_cible": str(montant_cible),
                "total_alloue": str(total_alloue),
            },
        )
        return fr

    for prop in propositions:
        LenderConsentRequest.objects.create(
            funding_request=fr,
            lender=prop.lender,
            tranche=prop.tranche,
            montant_propose=prop.montant,
            deadline=deadline,
        )

    record_audit(
        action="loan.funding.requested",
        entite_type="LoanFundingRequest",
        entite_id=fr.id,
        user=actor,
        details={
            "loan_id": loan.id,
            "montant_cible": str(montant_cible),
            "nb_lenders": len(propositions),
            "strategy": strategy,
            "deadline": deadline.isoformat(),
        },
    )

    # Notifications parallèles aux prêteurs (best-effort).
    _notify_lenders(fr)
    return fr


def _notify_lenders(fr: LoanFundingRequest) -> None:
    """Émet un événement ``loan.funding.consent_requested`` par prêteur (best-effort)."""
    try:
        from django.conf import settings

        from apps_coop.notifications.events import emit_event
    except Exception:  # noqa: BLE001 — système notifs indisponible
        return
    portal_url = getattr(settings, "FRONTEND_PUBLIC_URL", "")
    for cr in fr.consent_requests.select_related("lender", "lender__user").all():
        try:
            emit_event(
                "loan.funding.consent_requested",
                member=cr.lender,
                context={
                    "prenom": cr.lender.prenom,
                    "numero_membre": cr.lender.numero_membre,
                    "loan_dossier": fr.loan.numero_dossier,
                    "montant_propose": f"{int(cr.montant_propose):,}".replace(",", " "),
                    "deadline": cr.deadline.isoformat(),
                    # AUDIT-A2 . Template utilise {portal_url} dans CTA.
                    "portal_url": portal_url,
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "emit_event loan.funding.consent_requested failed (lender=%s)",
                cr.lender_id,
                exc_info=True,
            )


# ---------------------------------------------------------------------------
# Service — réponse d'un prêteur
# ---------------------------------------------------------------------------


@transaction.atomic
def respond_to_consent_request(
    *,
    consent_request: LenderConsentRequest,
    accept: bool,
    motif: str = "",
    actor=None,
) -> LenderConsentRequest:
    """Le prêteur répond explicitement (avant l'expiration).

    Idempotent : si déjà répondu (ACCEPTED/REFUSED/AUTO_ACCEPTED/OBSOLETE),
    renvoie l'objet inchangé. Sinon pose le statut et déclenche la
    finalisation si plus aucun PENDING dans la FR.
    """
    locked = LenderConsentRequest.objects.select_for_update().get(pk=consent_request.pk)
    if locked.statut != LenderConsentRequest.Statut.PENDING:
        return locked  # déjà traité

    now = timezone.now()
    if accept:
        locked.statut = LenderConsentRequest.Statut.ACCEPTED
    else:
        if not motif.strip():
            raise ValueError("Un motif est requis pour refuser.")
        locked.statut = LenderConsentRequest.Statut.REFUSED
        locked.refus_motif = motif.strip()
    locked.responded_at = now
    locked.save(update_fields=["statut", "refus_motif", "responded_at", "updated_at"])

    record_audit(
        action="loan.funding.consent.accepted" if accept else "loan.funding.consent.refused",
        entite_type="LenderConsentRequest",
        entite_id=locked.id,
        user=actor,
        details={
            "funding_request_id": locked.funding_request_id,
            "lender_id": locked.lender_id,
            "montant": str(locked.montant_propose),
        },
    )

    # Si plus aucun PENDING dans cette vague, on peut finaliser ou ré-allouer.
    fr = LoanFundingRequest.objects.select_for_update().get(pk=locked.funding_request_id)
    if not fr.consent_requests.filter(statut=LenderConsentRequest.Statut.PENDING).exists():
        _settle_wave(fr)
    return locked


# ---------------------------------------------------------------------------
# Cron — funding_window_expiry (toutes les ~15min, par défaut)
# ---------------------------------------------------------------------------


@transaction.atomic
def funding_window_expiry() -> dict:
    """Traite toutes les ``LoanFundingRequest`` dont la deadline est passée.

    Pose AUTO_ACCEPTED sur les ``LenderConsentRequest`` encore PENDING au-delà
    de leur propre deadline. Déclenche ensuite la finalisation pour les FR
    sans PENDING restant. Renvoie un compteur des actions effectuées (utile
    pour les logs cron).
    """
    now = timezone.now()
    auto_accepted = 0
    settled = 0
    skipped = 0

    expired_consents = (
        LenderConsentRequest.objects
        .select_for_update()
        .filter(statut=LenderConsentRequest.Statut.PENDING, deadline__lt=now)
    )
    for cr in expired_consents:
        cr.statut = LenderConsentRequest.Statut.AUTO_ACCEPTED
        cr.responded_at = now
        cr.save(update_fields=["statut", "responded_at", "updated_at"])
        auto_accepted += 1

    # Finalise toutes les FR dont la vague est entièrement traitée.
    waiting_frs = (
        LoanFundingRequest.objects
        .select_for_update()
        .filter(statut__in=[
            LoanFundingRequest.Statut.PENDING,
            LoanFundingRequest.Statut.REALLOCATING,
        ])
    )
    for fr in waiting_frs:
        if fr.consent_requests.filter(statut=LenderConsentRequest.Statut.PENDING).exists():
            skipped += 1
            continue
        _settle_wave(fr)
        settled += 1

    return {"auto_accepted": auto_accepted, "settled": settled, "skipped": skipped}


# ---------------------------------------------------------------------------
# Finalisation d'une vague (interne)
# ---------------------------------------------------------------------------


def _settle_wave(fr: LoanFundingRequest) -> None:
    """Décide quoi faire quand une vague est entièrement traitée.

    • Pas de REFUSED → finalise (FUNDED + allocations + tranches ENGAGEE)
    • Au moins un REFUSED → tente une vague suivante (réallocation)
    """
    has_refused = fr.consent_requests.filter(
        statut=LenderConsentRequest.Statut.REFUSED
    ).exists()
    if not has_refused:
        _finalize_funded(fr)
    else:
        _reallocate(fr)


@transaction.atomic
def _finalize_funded(fr: LoanFundingRequest) -> None:
    """Pose les allocations définitives, engage les tranches, FUNDED."""
    now = timezone.now()
    accepted = list(
        fr.consent_requests.filter(
            statut__in=[
                LenderConsentRequest.Statut.ACCEPTED,
                LenderConsentRequest.Statut.AUTO_ACCEPTED,
            ]
        ).select_related("lender")
    )
    total = sum((Decimal(c.montant_propose) for c in accepted), Decimal("0"))
    if total < Decimal(fr.montant_total):
        # Vague techniquement OK mais montant non couvert — bascule en attente.
        fr.statut = LoanFundingRequest.Statut.EN_ATTENTE_FUNDING
        fr.finalized_at = now
        fr.save(update_fields=["statut", "finalized_at", "updated_at"])
        record_audit(
            action="loan.funding.short",
            entite_type="LoanFundingRequest",
            entite_id=fr.id,
            details={"total": str(total), "cible": str(fr.montant_total)},
        )
        return

    for cr in accepted:
        # Posage de l'allocation + matérialisation de la tranche.
        if cr.tranche is not None:
            tranche = LenderTranche.objects.select_for_update().get(pk=cr.tranche_id)
            tranche.statut = LenderTranche.Statut.ENGAGEE
            tranche.engaged_in_loan = fr.loan
            tranche.engaged_at = now
            tranche.save(
                update_fields=[
                    "statut",
                    "engaged_in_loan",
                    "engaged_at",
                    "updated_at",
                ]
            )
        else:
            # Mode A — création d'une tranche dédiée à l'engagement.
            tranche = LenderTranche.objects.create(
                member=cr.lender,
                montant=cr.montant_propose,
                statut=LenderTranche.Statut.ENGAGEE,
                engaged_in_loan=fr.loan,
                engaged_at=now,
            )

        quote_part = (Decimal(cr.montant_propose) / Decimal(fr.montant_total)).quantize(
            Decimal("0.00000001")
        )
        LenderAllocation.objects.create(
            loan=fr.loan,
            lender=cr.lender,
            tranche=tranche,
            montant_alloue=cr.montant_propose,
            quote_part=quote_part,
        )

    fr.statut = LoanFundingRequest.Statut.FUNDED
    fr.finalized_at = now
    fr.save(update_fields=["statut", "finalized_at", "updated_at"])

    record_audit(
        action="loan.funding.funded",
        entite_type="LoanFundingRequest",
        entite_id=fr.id,
        details={
            "loan_id": fr.loan_id,
            "nb_allocations": len(accepted),
            "montant_total": str(fr.montant_total),
        },
    )

    try:
        from django.conf import settings

        from apps_coop.notifications.events import emit_event

        emit_event(
            "loan.funding.completed",
            member=fr.loan.member,
            context={
                "prenom": fr.loan.member.prenom,
                "loan_dossier": fr.loan.numero_dossier,
                "montant": f"{int(fr.montant_total):,}".replace(",", " "),
                # AUDIT-A2 . Template utilise {portal_url} dans CTA.
                "portal_url": getattr(settings, "FRONTEND_PUBLIC_URL", ""),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("emit_event loan.funding.completed failed", exc_info=True)


@transaction.atomic
def _reallocate(fr: LoanFundingRequest) -> None:
    """Tente une nouvelle vague avec des prêteurs de remplacement.

    Calcule le déficit (= montant total - accepté ferme), cherche des
    prêteurs non sollicités jusqu'ici, crée de nouvelles consent requests
    pour la vague suivante. Si déficit non couvrable → EN_ATTENTE_FUNDING.
    """
    now = timezone.now()
    deficit = Decimal(fr.montant_total) - (
        fr.consent_requests.filter(
            statut__in=[
                LenderConsentRequest.Statut.ACCEPTED,
                LenderConsentRequest.Statut.AUTO_ACCEPTED,
            ]
        ).aggregate(s=Sum("montant_propose"))["s"]
        or Decimal("0")
    )
    if deficit <= 0:
        # Surcouverture (rare) — finalise quand même.
        _finalize_funded(fr)
        return

    # Marque les vagues précédentes comme OBSOLETE n'est PAS nécessaire ici :
    # les REFUSED restent REFUSED, on ne touche pas aux ACCEPTED. On exclut
    # simplement les lenders déjà sollicités (peu importe leur statut).
    excluded = set(
        fr.consent_requests.values_list("lender_id", flat=True).distinct()
    )

    candidates = list(active_lenders_with_capacity())
    new_propositions = _allocate(
        montant_cible=deficit,
        candidates=candidates,
        strategy=fr.strategy,
        excluded_lender_ids=excluded,
    )
    new_total = sum((p.montant for p in new_propositions), Decimal("0"))

    if new_total < deficit:
        # Pas de remplaçants suffisants → bascule attente intervention admin.
        fr.statut = LoanFundingRequest.Statut.EN_ATTENTE_FUNDING
        fr.finalized_at = now
        fr.save(update_fields=["statut", "finalized_at", "updated_at"])
        record_audit(
            action="loan.funding.exhausted",
            entite_type="LoanFundingRequest",
            entite_id=fr.id,
            details={
                "deficit": str(deficit),
                "new_total": str(new_total),
                "wave": fr.wave_number,
            },
        )
        try:
            from django.conf import settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "loan.funding.exhausted",
                member=fr.loan.member,
                context={
                    "prenom": fr.loan.member.prenom,
                    "loan_dossier": fr.loan.numero_dossier,
                    "deficit": f"{int(deficit):,}".replace(",", " "),
                    # AUDIT-A2 . Template utilise {portal_url} dans CTA.
                    "portal_url": getattr(settings, "FRONTEND_PUBLIC_URL", ""),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning("emit_event loan.funding.exhausted failed", exc_info=True)
        return

    # Nouvelle vague : incrément + nouvelle deadline + nouvelles consents.
    fr.wave_number += 1
    fr.deadline = now + timedelta(hours=_window_hours())
    fr.statut = LoanFundingRequest.Statut.REALLOCATING
    fr.save(update_fields=["wave_number", "deadline", "statut", "updated_at"])

    for prop in new_propositions:
        LenderConsentRequest.objects.create(
            funding_request=fr,
            lender=prop.lender,
            tranche=prop.tranche,
            montant_propose=prop.montant,
            deadline=fr.deadline,
        )

    record_audit(
        action="loan.funding.reallocated",
        entite_type="LoanFundingRequest",
        entite_id=fr.id,
        details={
            "wave": fr.wave_number,
            "deficit": str(deficit),
            "nb_new_lenders": len(new_propositions),
        },
    )
    _notify_lenders(fr)
