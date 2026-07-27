"""Routeur d'éligibilité 3 voies (refonte 2026 §7.1 / LOT 12).

Décide quelle **voie** s'applique à une demande de crédit :

  * **Voie 1 — SENIOR_BRC** : deux chemins directs (sans avaliste) —
    (a) **auto-couverture** : épargne classique disponible ≥ montant ; ou
    (b) **ancien + BRC** : ancienneté ≥ ``seniority.threshold_months`` ET statut
    BRC validé → passe en instruction **même sous-couvert**, c'est le comité qui
    juge (crédit de confiance).
  * **Voie 2 — AVALISTE** : nouvel adhérent avec un avaliste senior désigné
    et couverture épargne ≥ ``loans.avaliste.min_coverage_ratio``.
  * **Voie 3 — MICROCAMPAIGN** : non-adhérent dans une campagne ouverte au
    profil ciblé (montant ∈ bornes, quota non atteint).
  * **NONE** : aucune voie ne s'applique → rejet auto avec motifs cumulés.

**API pure** (read-only) — aucun side-effect, aucune écriture en base. Le
service qui matérialise la ``LoanRequest`` consomme le résultat et choisit
la voie. Cela rend l'éval testable, idempotente et fanout-friendly.

**Tunables admin** (libre arbitre — toggler/désactiver chaque voie sans
deploiement) :

  - ``loans.eligibility.allow_senior_brc`` (true) — kill-switch Voie 1
  - ``loans.eligibility.allow_avaliste`` (true) — kill-switch Voie 2
  - ``loans.eligibility.allow_campaign`` (true) — kill-switch Voie 3
  - ``loans.eligibility.require_brc_for_senior`` (**false** par défaut depuis
    2026-07) — le BRC est devenu documentaire (plus de validation) : l'ancienneté
    seule débloque la Voie 1, le comité juge la demande en consultant la pièce.
    Repasser à true si l'admin veut re-exiger un statut BRC validé.
  - ``loans.eligibility.route_priority`` (csv "senior_brc,avaliste,campaign")
    — admin peut réordonner. Une voie absente est désactivée.

LOT 13 wirera ``evaluate_routes`` dans la création effective d'une
``LoanRequest`` (création du Member TEMPORAIRE pour la voie campagne, etc.).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db.models import QuerySet

from apps_coop.audit.services import get_str_setting
from apps_coop.members.models import Member

from .models import MicrocreditCampaign


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums et structures publiques
# ---------------------------------------------------------------------------


class EligibilityRoute:
    """Constantes de voie — strings pour faciliter sérialisation REST/JSON."""

    SENIOR_BRC = "senior_brc"
    AVALISTE = "avaliste"
    GARANTIE_MATERIELLE = "garantie_materielle"
    CAMPAIGN = "campaign"
    NONE = "none"


@dataclass
class RouteEvaluation:
    """Résultat structuré de ``evaluate_routes``.

    ``route``        : voie retenue (ou ``NONE``).
    ``eligible``     : booléen miroir de ``route != NONE``.
    ``motifs``       : liste des raisons de rejet/contexte (UI peut afficher).
    ``details``      : metadata par voie (ex. ratio couverture, campaign_id).
    ``suggested_campaigns`` : campagnes actives matchant le profil (pour
                       proposer à l'utilisateur s'il n'a pas désigné une voie).
    """

    route: str
    eligible: bool
    motifs: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    suggested_campaigns: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AppSettings helpers — kill-switches + priorité
# ---------------------------------------------------------------------------


def _bool_setting(key: str, default: bool = True) -> bool:
    """Lit un AppSetting str ``"true"``/``"false"`` (casse-insensible)."""
    raw = (get_str_setting(key, "true" if default else "false") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _decimal_setting(key: str, default: Decimal) -> Decimal:
    """Lit un AppSetting décimal (ex. un taux ``"0.30"``). Retombe sur ``default``
    si absent ou illisible."""
    raw = get_str_setting(key, str(default))
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError):
        return default


def _route_priority() -> list[str]:
    """Retourne l'ordre d'évaluation des voies (admin-tunable).

    Défaut : ``["senior_brc", "avaliste", "campaign"]`` (ordre §7.1). Une
    voie absente de la liste est de fait **désactivée**. Cumulé avec les
    kill-switches ``allow_*``.
    """
    raw = get_str_setting(
        "loans.eligibility.route_priority",
        "senior_brc,avaliste,garantie_materielle,campaign",
    )
    parts = [p.strip().lower() for p in (raw or "").split(",") if p.strip()]
    valid = {
        EligibilityRoute.SENIOR_BRC,
        EligibilityRoute.AVALISTE,
        EligibilityRoute.GARANTIE_MATERIELLE,
        EligibilityRoute.CAMPAIGN,
    }
    return [p for p in parts if p in valid] or [
        EligibilityRoute.SENIOR_BRC,
        EligibilityRoute.AVALISTE,
        EligibilityRoute.GARANTIE_MATERIELLE,
        EligibilityRoute.CAMPAIGN,
    ]


# ---------------------------------------------------------------------------
# Évaluateurs par voie — purs (aucun side-effect)
# ---------------------------------------------------------------------------


@dataclass
class _VoieResult:
    matched: bool
    motifs: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def _eval_senior_brc(
    member: Member,
    montant: Decimal,
    *,
    extra_payload: Optional[dict] = None,
) -> _VoieResult:
    """Voie 1 — AUTO-COUVERTURE **ou** ANCIEN + BRC (jugé par le comité).

    Deux chemins directs, **sans avaliste** :

      1. **Auto-couverture** — l'épargne classique DISPONIBLE du demandeur couvre
         le montant : ``épargne disponible ≥ montant``. Le placement en cours
         compte dans l'épargne (il sera gelé en garantie). Un nouvel adhérent qui
         se couvre lui-même n'a pas besoin d'avaliste.

      2. **Ancien** — membre établi (``seniority_months ≥
         seniority.threshold_months``). La demande passe en instruction **même
         sous-couverte** : c'est le COMITÉ DES PRÊTS qui juge la validité (crédit
         de confiance, comme la garantie matérielle et la campagne), en
         consultant le justificatif BRC désormais **documentaire**. Le réglage
         ``loans.eligibility.require_brc_for_senior`` (défaut **false**) : si
         true, l'admin re-exige un statut BRC validé (``is_brc_member``).

    Le montant réellement gelé côté demandeur est décidé à la création
    (``min(montant, épargne disponible)``) : un ancien sous-couvert immobilise ce
    qu'il a, pas plus — le reste est un pari de confiance tranché par le comité.
    """
    if not _bool_setting("loans.eligibility.allow_senior_brc", True):
        return _VoieResult(
            matched=False,
            motifs=["Voie auto-couverture / ancien désactivée par l'admin."],
        )

    from apps_coop.audit.services import get_int_setting

    from .avaliste_services import _member_available_savings

    montant_d = Decimal(montant)
    if montant_d <= 0:
        return _VoieResult(
            matched=False,
            motifs=["Montant demandé invalide pour la voie auto-couverture / ancien."],
        )

    epargne = _member_available_savings(member)

    # Apport personnel (2026-07) : l'éligibilité n'exige plus une couverture à
    # 100 %. Il suffit que l'épargne classique DISPONIBLE atteigne le taux
    # d'apport requis (``loans.eligibility.apport_rate``, défaut 0.30) du montant.
    # Le comité juge le reste (sous-couverture), comme la voie « ancien ».
    apport_rate = _decimal_setting("loans.eligibility.apport_rate", Decimal("0.30"))
    apport_requis = (montant_d * apport_rate).quantize(Decimal("1"))

    # Chemin 1a — auto-couverture PLEINE (l'épargne dispo couvre tout : 0 risque).
    if epargne >= montant_d:
        return _VoieResult(
            matched=True,
            details={
                "epargne_disponible": str(epargne),
                "montant": str(montant_d),
                "apport_rate": str(apport_rate),
                "apport_requis": str(apport_requis),
                "auto_couverture": True,
            },
        )

    # Chemin 1b — APPORT suffisant (épargne ≥ apport_rate × montant) : éligible,
    # mais sous-couvert → signalé au comité, qui tranche.
    if epargne >= apport_requis:
        return _VoieResult(
            matched=True,
            details={
                "epargne_disponible": str(epargne),
                "montant": str(montant_d),
                "apport_rate": str(apport_rate),
                "apport_requis": str(apport_requis),
                "apport_couverture": True,
                "sous_couverture": True,
                "manque": str(montant_d - epargne),
            },
        )

    # Chemin 2 — ancien (+ BRC) : la couverture n'est PAS exigée, le comité juge.
    threshold = get_int_setting("seniority.threshold_months", 12)
    # Défaut 2026-07 : le BRC n'est plus un statut à valider (pièce purement
    # documentaire, consultée par le comité). L'ancienneté seule ouvre donc la
    # voie « crédit de confiance » ; le comité juge la demande. L'admin peut
    # re-exiger un BRC validé en repassant ce réglage à true.
    require_brc = _bool_setting("loans.eligibility.require_brc_for_senior", False)
    seniority = int(getattr(member, "seniority_months", 0) or 0)
    has_brc = bool(getattr(member, "is_brc_member", False))
    is_senior = seniority >= threshold

    if is_senior and (has_brc or not require_brc):
        return _VoieResult(
            matched=True,
            details={
                "epargne_disponible": str(epargne),
                "montant": str(montant_d),
                "senior_brc": True,
                # Signalé au comité : dossier sous-couvert, accordé sur confiance.
                "sous_couverture": True,
                "manque": str(montant_d - epargne),
                "seniority_months": seniority,
                "brc_valide": has_brc,
            },
        )

    # Ni apport suffisant, ni ancien+BRC éligible.
    motifs = [
        f"Épargne classique disponible insuffisante : {epargne} XAF < apport "
        f"requis {apport_requis} XAF ({apport_rate * 100:.0f}% du montant "
        f"{montant_d} XAF)."
    ]
    if not is_senior:
        motifs.append(
            f"Ancienneté insuffisante pour un crédit de confiance sans garantie "
            f"({seniority} mois < {threshold})."
        )
    elif require_brc and not has_brc:
        motifs.append(
            "Statut BRC non validé — requis pour un crédit de confiance sans "
            "couverture épargne."
        )
    motifs.append("Désigne un avaliste ancien pour compléter, ou baisse le montant.")
    return _VoieResult(
        matched=False,
        motifs=motifs,
        details={
            "epargne_disponible": str(epargne),
            "montant": str(montant_d),
        },
    )


def _eval_avaliste(
    member: Member,
    montant: Decimal,
    *,
    avaliste_numero: Optional[str],
    avaliste_nom: Optional[str],
) -> _VoieResult:
    """Voie 2 — AVALISTE. Évalue *sans créer* d'``AvalisteConsent``.

    Vérifie : voie activée + identification résoluble + couverture épargne
    suffisante + auto-désignation interdite. Le consentement réel sera
    posé par ``avaliste_services.request_avaliste_consent`` à l'étape
    suivante (LOT 13 wiring).
    """
    if not _bool_setting("loans.eligibility.allow_avaliste", True):
        return _VoieResult(
            matched=False,
            motifs=["Voie AVALISTE désactivée par l'admin."],
        )
    if not avaliste_numero or not avaliste_nom:
        return _VoieResult(
            matched=False,
            motifs=["Voie AVALISTE non sollicitée (pas de désignation)."],
        )

    from .avaliste_services import (
        _member_available_savings,
        _min_coverage_ratio,
        find_avaliste,
    )

    try:
        avaliste = find_avaliste(avaliste_numero, avaliste_nom)
    except LookupError as exc:
        return _VoieResult(matched=False, motifs=[str(exc)])
    except ValueError as exc:
        return _VoieResult(matched=False, motifs=[str(exc)])

    if avaliste.pk == member.pk:
        return _VoieResult(
            matched=False,
            motifs=["Le demandeur ne peut pas être son propre avaliste."],
        )

    montant_d = Decimal(montant)
    if montant_d <= 0:
        return _VoieResult(
            matched=False,
            motifs=["Montant demandé invalide pour évaluer la voie AVALISTE."],
        )

    # Épargnes DISPONIBLES (classique − gel déjà pris) — anti double-nantissement.
    eb = _member_available_savings(member)
    ea = _member_available_savings(avaliste)
    total = eb + ea
    ratio = (total / montant_d).quantize(Decimal("0.0001"))
    min_ratio = _min_coverage_ratio()

    if ratio < min_ratio:
        return _VoieResult(
            matched=False,
            motifs=[
                f"Couverture épargne insuffisante : {ratio} < {min_ratio}. "
                f"Cumul épargnes {total} XAF / montant {montant_d} XAF."
            ],
            details={
                "avaliste_id": avaliste.id,
                "epargne_borrower": str(eb),
                "epargne_avaliste": str(ea),
                "couverture_ratio": str(ratio),
                "min_ratio": str(min_ratio),
            },
        )

    return _VoieResult(
        matched=True,
        details={
            "avaliste_id": avaliste.id,
            "avaliste_numero": avaliste.numero_membre,
            "couverture_ratio": str(ratio),
            "min_ratio": str(min_ratio),
        },
    )


def _eval_garantie_materielle(
    member: Member,
    montant: Decimal,
    *,
    garantie_materielle: bool,
) -> _VoieResult:
    """Voie GARANTIE MATÉRIELLE (L4) — fallback sans avaliste.

    Matche dès que le demandeur déclare s'appuyer sur une garantie matérielle
    (bien, ex. titre de propriété). La couverture réelle (valeur du bien ≥
    montant) n'est PAS vérifiée ici : elle est **différée** à l'évaluation
    manuelle de la commission puis contrôlée à l'approbation
    (``approve_loan_request``). C'est un chemin d'instruction, comme la
    campagne où la décision finale appartient à l'admin.
    """
    if not _bool_setting("loans.eligibility.allow_garantie_materielle", True):
        return _VoieResult(
            matched=False,
            motifs=["Voie garantie matérielle désactivée par l'admin."],
        )
    if not garantie_materielle:
        return _VoieResult(
            matched=False,
            motifs=["Voie GARANTIE MATÉRIELLE non sollicitée (pas de bien déclaré)."],
        )
    montant_d = Decimal(montant)
    if montant_d <= 0:
        return _VoieResult(
            matched=False,
            motifs=["Montant demandé invalide pour la voie garantie matérielle."],
        )
    return _VoieResult(
        matched=True,
        details={"garantie_materielle": True, "montant": str(montant_d)},
    )


def _eval_campaign(
    member: Member,
    montant: Decimal,
    *,
    campaign_id: Optional[int],
    profil_cible: Optional[str],
) -> _VoieResult:
    """Voie 3 — MICROCAMPAIGN.

    Si ``campaign_id`` est fourni, valide cette campagne précise. Sinon
    cherche une campagne active dont le profil match ``profil_cible`` (ou
    n'importe laquelle si le profil n'est pas spécifié).
    """
    if not _bool_setting("loans.eligibility.allow_campaign", True):
        return _VoieResult(
            matched=False,
            motifs=["Voie MICROCAMPAIGN désactivée par l'admin."],
        )

    from .microcampaign_services import (
        get_active_campaigns,
        is_campaign_open,
        validate_amount_against_campaign,
    )

    montant_d = Decimal(montant)
    if montant_d <= 0:
        return _VoieResult(
            matched=False,
            motifs=["Montant demandé invalide pour évaluer la voie CAMPAGNE."],
        )

    # 1) Campagne explicitement désignée
    if campaign_id:
        try:
            campaign = MicrocreditCampaign.objects.get(pk=campaign_id)
        except MicrocreditCampaign.DoesNotExist:
            return _VoieResult(
                matched=False,
                motifs=[f"Campagne #{campaign_id} introuvable."],
            )
        if not is_campaign_open(campaign):
            return _VoieResult(
                matched=False,
                motifs=[f"Campagne #{campaign_id} fermée."],
            )
        try:
            validate_amount_against_campaign(campaign, montant_d)
        except ValueError as exc:
            return _VoieResult(matched=False, motifs=[str(exc)])
        return _VoieResult(
            matched=True,
            details={
                "campaign_id": campaign.id,
                "campagne": campaign.nom,
                "taux_interet": str(campaign.taux_interet),
                "profil_cible": campaign.profil_cible,
            },
        )

    # 2) Recherche d'une campagne par profil_cible
    qs: QuerySet[MicrocreditCampaign] = get_active_campaigns(
        profil_cible=profil_cible
    )
    candidates = list(qs[:5])
    if not candidates:
        return _VoieResult(
            matched=False,
            motifs=[
                "Aucune campagne micro-crédit active ne correspond"
                + (f" au profil '{profil_cible}'." if profil_cible else ".")
            ],
        )

    # On retient la première campagne qui passe la validation montant/quota.
    for c in candidates:
        try:
            validate_amount_against_campaign(c, montant_d)
        except ValueError:
            continue
        return _VoieResult(
            matched=True,
            details={
                "campaign_id": c.id,
                "campagne": c.nom,
                "taux_interet": str(c.taux_interet),
                "profil_cible": c.profil_cible,
            },
        )

    # Pas de campagne compatible — on rend les IDs pour suggestion.
    return _VoieResult(
        matched=False,
        motifs=[
            "Aucune campagne active ne valide votre montant (hors bornes ou "
            "quota saturé)."
        ],
        details={"suggested_campaigns": [c.id for c in candidates]},
    )


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def _chosen_voie(
    *,
    avaliste_numero: Optional[str],
    avaliste_nom: Optional[str],
    campaign_id: Optional[int],
    profil_cible: Optional[str],
    garantie_materielle: bool,
) -> str:
    """Voie CHOISIE par le membre, déduite de ce qu'il a renseigné.

    Le membre pilote sa voie : campagne (id de campagne OU profil ciblé rempli),
    avaliste (désigne un garant), garantie matérielle (déclare un bien). S'il ne
    désigne rien, c'est la voie par défaut SENIOR_BRC (auto-couverture épargne /
    ancienneté). On ne laisse PLUS une autre voie « voler » ce choix (fini le
    « je choisis X mais Y s'affiche »)."""
    if campaign_id or (profil_cible or "").strip():
        return EligibilityRoute.CAMPAIGN
    if (avaliste_numero or "").strip() and (avaliste_nom or "").strip():
        return EligibilityRoute.AVALISTE
    if garantie_materielle:
        return EligibilityRoute.GARANTIE_MATERIELLE
    return EligibilityRoute.SENIOR_BRC


def evaluate_routes(
    member: Member,
    *,
    montant: Decimal,
    avaliste_numero: Optional[str] = None,
    avaliste_nom: Optional[str] = None,
    campaign_id: Optional[int] = None,
    profil_cible: Optional[str] = None,
    garantie_materielle: bool = False,
    extra_payload: Optional[dict] = None,
) -> RouteEvaluation:
    """Évalue **la voie CHOISIE par le membre** (déduite de ses saisies), et
    elle seule — la voie affichée sur la demande est toujours celle choisie.

    On ne parcourt plus les voies par ordre de priorité en prenant « la première
    qui matche » : ça faisait qu'un ancien qui postulait à une campagne (ou
    désignait un avaliste) se retrouvait routé en SENIOR_BRC. Désormais :

      * campagne désignée → voie CAMPAIGN ;
      * avaliste désigné  → voie AVALISTE ;
      * bien déclaré      → voie GARANTIE_MATERIELLE ;
      * rien              → voie SENIOR_BRC (auto-couverture / ancienneté).

    Une voie retirée de ``loans.eligibility.route_priority`` (ou coupée par son
    ``allow_*``) reste désactivée. Si la voie choisie échoue, on renvoie NONE
    avec SES motifs (on ne bascule pas en douce sur une autre voie)."""
    chosen = _chosen_voie(
        avaliste_numero=avaliste_numero,
        avaliste_nom=avaliste_nom,
        campaign_id=campaign_id,
        profil_cible=profil_cible,
        garantie_materielle=garantie_materielle,
    )

    # Kill-switch par liste : une voie absente de la priorité admin est désactivée.
    if chosen not in set(_route_priority()):
        return RouteEvaluation(
            route=EligibilityRoute.NONE,
            eligible=False,
            motifs=[f"Voie « {chosen} » désactivée par l'administration."],
        )

    if chosen == EligibilityRoute.CAMPAIGN:
        r = _eval_campaign(
            member, montant, campaign_id=campaign_id, profil_cible=profil_cible
        )
    elif chosen == EligibilityRoute.AVALISTE:
        r = _eval_avaliste(
            member,
            montant,
            avaliste_numero=avaliste_numero,
            avaliste_nom=avaliste_nom,
        )
    elif chosen == EligibilityRoute.GARANTIE_MATERIELLE:
        r = _eval_garantie_materielle(
            member, montant, garantie_materielle=garantie_materielle
        )
    else:  # SENIOR_BRC
        r = _eval_senior_brc(member, montant, extra_payload=extra_payload)

    if r.matched:
        return RouteEvaluation(
            route=chosen, eligible=True, motifs=[], details=r.details
        )

    return RouteEvaluation(
        route=EligibilityRoute.NONE,
        eligible=False,
        motifs=[f"[{chosen}] {m}" for m in r.motifs]
        or ["Aucune voie d'éligibilité applicable. Contactez la coopérative."],
        details={chosen: r.details},
        suggested_campaigns=r.details.get("suggested_campaigns", []),
    )
