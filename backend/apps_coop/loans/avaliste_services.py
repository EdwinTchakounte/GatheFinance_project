"""Voie 2 — AVALISTE (refonte 2026 §7.2 / LOT 10).

Trois fonctions publiques :
  * ``find_avaliste(numero, nom)`` — résolution + validations d'identification.
    Renvoie le ``Member`` ancien, ou lève ``ValueError``/``LookupError`` en cas
    de mismatch (numéro inconnu, nom incorrect, pas senior, pas actif).
  * ``request_avaliste_consent(loan_request, numero, nom)`` — pose
    ``AvalisteConsent`` + bascule la ``LoanRequest`` en ``EN_ATTENTE_AVALISTE``.
    Vérifie la couverture épargne et refuse en amont si elle est insuffisante.
  * ``respond_to_avaliste_consent(consent, accept, motif)`` — réponse de
    l'avaliste. Accept → ``LoanRequest.avaliste = avaliste`` + statut
    ``EN_INSTRUCTION``. Refuse → statut terminal ``REJETEE_AVALISTE``.

Note Q13 : pas de rétractation après ACCEPTED. La fonction est idempotente
sur la première décision et lève ``ValueError`` sur une seconde tentative
de changement.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import (
    get_str_setting,
    record as record_audit,
)
from apps_coop.members.models import Member

from .guarantee_tranches import earmark_guarantee_tranches
from .models import AvalisteConsent, LoanRequest


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _min_coverage_ratio() -> Decimal:
    """Ratio minimum (épargne X + épargne avaliste) / montant_demande.

    Tunable via AppSetting ``loans.avaliste.min_coverage_ratio`` (défaut 1.00).
    """
    raw = get_str_setting("loans.avaliste.min_coverage_ratio", "1.00")
    try:
        ratio = Decimal(str(raw).strip())
    except Exception:  # noqa: BLE001
        logger.warning(
            "loans.avaliste.min_coverage_ratio invalide (%r), fallback 1.00",
            raw,
        )
        ratio = Decimal("1.00")
    return max(Decimal("0"), ratio)


# Statuts de LoanRequest où le gel du collatéral demandeur est LIBÉRÉ
# (dossier mort). Tout autre statut = gel vivant tant que le Loan associé
# n'est pas CLOTURE. Sert aussi de règle de libération aux tranches GELEE
# (cf. apps_coop.loans.signals).
def _released_request_statuses():
    from .models import LoanRequest

    return {
        LoanRequest.Statut.REJETEE,
        LoanRequest.Statut.REJETEE_AVALISTE,
        LoanRequest.Statut.REJETEE_CAMPAGNE,
    }


def _member_total_savings(member: Member) -> Decimal:
    """Solde-garantie du membre = **épargne classique** (libre + placement).

    Refonte 2026 (réforme garantie) : la collecte journalière est EXCLUE (elle
    est reversée chaque fin de mois, donc non mobilisable en garantie). Seule
    l'épargne classique — part libre + placement bloqué — sert de garantie
    (crédit avaliste ou auto-couverture).

    Renvoie 0 si aucun compte classique n'existe. Ne lève jamais — lecture
    seule pour la couverture, pas pour un débit.
    """
    try:
        if hasattr(member, "classic_savings_account"):
            return Decimal(member.classic_savings_account.solde)
    except Exception:  # noqa: BLE001 — table non migrée / compte absent
        pass
    return Decimal("0")


def _borrower_frozen_amount(member: Member) -> Decimal:
    """Épargne classique propre gelée par ce membre comme DEMANDEUR.

    Somme des ``LoanRequest.montant_gele_demandeur`` de ses demandes encore
    vivantes (ni rejetées, ni adossées à un Loan CLOTURE). C'est le collatéral
    que le demandeur immobilise sur ses propres crédits.
    """
    from .models import Loan, LoanRequest

    total = Decimal("0")
    released = _released_request_statuses()
    reqs = (
        LoanRequest.objects.filter(member=member)
        .exclude(statut__in=released)
        .select_related("loan")
    )
    for lr in reqs:
        loan = getattr(lr, "loan", None)
        if loan is not None and loan.statut == Loan.Statut.CLOTURE:
            continue  # crédit soldé → collatéral libéré
        total += Decimal(lr.montant_gele_demandeur or 0)
    return total


def _avaliste_frozen_amount(avaliste: Member) -> Decimal:
    """Épargne classique gelée par ce membre en tant qu'AVALISTE.

    Somme des ``AvalisteConsent.montant_caution`` (le manque réellement
    engagé) ACCEPTÉS dont le Loan n'est pas encore CLOTURE. Une caution est
    libérée à la clôture du crédit garanti.

    Cas :
      - PENDING → pas encore engagé (zéro).
      - REFUSED → refusé (zéro).
      - ACCEPTED, demande rejetée/terminée sans Loan (ex. **rejet comité après
        acceptation avaliste**) → LIBÉRÉ (comme le collatéral demandeur).
      - ACCEPTED sans Loan (instruction en cours) → compté (engagement pris).
      - ACCEPTED + Loan CLOTURE → libéré.

    NB : on aligne la libération sur ``_borrower_frozen_amount`` — sinon une
    caution acceptée puis rejetée par le comité restait gelée « à vie » alors
    que les tranches persistées étaient, elles, bien libérées par le signal.
    """
    from .models import AvalisteConsent, Loan

    total = Decimal("0")
    released = _released_request_statuses()
    consents = AvalisteConsent.objects.filter(
        avaliste=avaliste,
        statut=AvalisteConsent.Statut.ACCEPTED,
    ).select_related("loan_request", "loan_request__loan")
    for c in consents:
        lr = c.loan_request
        # Demande dans un statut « libéré » (rejetée demandeur/avaliste/campagne)
        # → la caution n'est plus engagée, même si aucun Loan n'a été créé.
        if lr is not None and lr.statut in released:
            continue
        loan = getattr(lr, "loan", None)
        if loan is not None and loan.statut == Loan.Statut.CLOTURE:
            continue  # caution libérée
        total += Decimal(c.montant_caution or 0)
    return total


def member_frozen_guarantee(member: Member, *, effective: bool = True) -> Decimal:
    """Total de l'épargne classique gelée par ce membre (demandeur + avaliste).

    Utilisé par le retrait épargne classique pour « griser » cette part :
    withdrawable = solde − max(placement_actif, ce gel).

    INTÉGRITÉ (2026-07) : le gel *effectif* est **borné à l'épargne classique
    réellement présente**. On ne peut pas geler plus que ce qui existe : un
    engagement de gel qui dépasse le solde (collatéral érodé depuis la demande,
    ex. placement restitué) devient un *déficit de collatéral*, pas un gel
    fantôme qui « grise » plus que le solde. Ainsi le nombre affiché et le
    disponible calculé restent toujours cohérents (jamais gel > solde).

    ``effective=False`` renvoie l'engagement brut (somme des snapshots), utile
    pour mesurer un éventuel déficit de couverture.
    """
    raw = _borrower_frozen_amount(member) + _avaliste_frozen_amount(member)
    if not effective:
        return raw
    solde = _member_total_savings(member)
    if solde <= 0:
        return Decimal("0")
    return raw if raw < solde else solde


def _member_available_savings(member: Member) -> Decimal:
    """Épargne classique DISPONIBLE = solde classique − gel garantie déjà pris.

    Empêche le double-nantissement : une épargne déjà gelée sur un crédit
    vivant ne peut pas re-servir de garantie à un nouveau crédit.
    """
    free = _member_total_savings(member) - member_frozen_guarantee(member)
    return free if free > 0 else Decimal("0")


def member_cagnotte(member: Member) -> Decimal:
    """Cagnotte disponible du membre = épargne classique **non gelée** (part
    libre + placement) + **collecte journalière**.

    Base du garde-fou « apport personnel » (2026-07) : la demande de crédit est
    refusée automatiquement si cette cagnotte ne couvre pas l'apport minimum
    requis. À la différence de la garantie (``_member_total_savings`` exclut la
    collecte), l'apport TIENT COMPTE de la collecte — c'est de l'épargne
    mobilisable côté membre, même si elle est reversée en fin de mois.
    """
    from apps_coop.savings.models import SavingsAccount

    dispo = _member_available_savings(member)
    collecte = (
        SavingsAccount.objects.filter(member=member)
        .values_list("solde", flat=True)
        .first()
    )
    if collecte:
        dispo += Decimal(collecte)
    return dispo if dispo > 0 else Decimal("0")


def _apport_rate() -> Decimal:
    """Taux d'apport personnel attendu (indicatif). AppSetting ``loans.apport.rate``."""
    raw = get_str_setting("loans.apport.rate", "0.20")
    try:
        return max(Decimal("0"), Decimal(str(raw).strip()))
    except Exception:  # noqa: BLE001
        logger.warning("loans.apport.rate invalide (%r), fallback 0.20", raw)
        return Decimal("0.20")


def _apport_min_available_rate() -> Decimal:
    """Seuil de rejet automatique. AppSetting ``loans.apport.min_available_rate``."""
    raw = get_str_setting("loans.apport.min_available_rate", "0.10")
    try:
        return max(Decimal("0"), Decimal(str(raw).strip()))
    except Exception:  # noqa: BLE001
        logger.warning(
            "loans.apport.min_available_rate invalide (%r), fallback 0.10", raw
        )
        return Decimal("0.10")


def member_caution_capacity(avaliste: Member) -> tuple[Decimal, Decimal, Decimal]:
    """Triplet ``(solde_total, cautions_engagees, capacite_restante)``.

    Helper public — utilisé par l'endpoint `search-avaliste/` pour exposer
    la dispo au mobile, et par `request_avaliste_consent` pour borner une
    nouvelle caution. ``capacite_restante`` = épargne classique DISPONIBLE
    (déduit tout ce que le membre a déjà gelé, comme demandeur ET avaliste).
    """
    solde = _member_total_savings(avaliste)
    engaged = member_frozen_guarantee(avaliste)
    free = solde - engaged
    if free < 0:
        free = Decimal("0")
    return solde, engaged, free


# ---------------------------------------------------------------------------
# Identification — find_avaliste
# ---------------------------------------------------------------------------


def find_avaliste(numero_identification: str, nom: str) -> Member:
    """Résout l'avaliste par double-clé numéro + nom.

    Lève :
      - ``LookupError`` si le numéro est inconnu.
      - ``ValueError`` si le nom ne correspond pas ou si le membre n'est pas
        ACTIF.

    Validation casse-insensible + trim sur ``nom`` (anti-faute de frappe).

    Réforme garantie 2026 : **aucune condition d'ancienneté**. Ce qui fait un
    avaliste valable, c'est sa capacité à immobiliser le montant — pas son
    âge dans la coopérative. Un membre de la cohorte 2026 avec l'épargne
    suffisante est un meilleur garant qu'un ancien à sec.
    """
    numero = (numero_identification or "").strip()
    nom_saisi = (nom or "").strip()
    if not numero or not nom_saisi:
        raise ValueError("Numéro et nom requis pour identifier l'avaliste.")

    avaliste = Member.objects.filter(numero_membre=numero).first()
    if avaliste is None:
        raise LookupError(f"Aucun membre trouvé avec le numéro {numero!r}.")

    if avaliste.nom.casefold() != nom_saisi.casefold():
        raise ValueError("Le nom de famille ne correspond pas au numéro fourni.")

    if avaliste.statut != Member.Statut.ACTIF:
        raise ValueError(
            f"Le membre {numero} n'est pas actif (statut: {avaliste.statut})."
        )

    return avaliste


# ---------------------------------------------------------------------------
# request_avaliste_consent — création
# ---------------------------------------------------------------------------


@transaction.atomic
def request_avaliste_consent(
    loan_request: LoanRequest,
    *,
    numero_identification: str,
    nom: str,
) -> AvalisteConsent:
    """Pose l'``AvalisteConsent`` + passe la LR en ``EN_ATTENTE_AVALISTE``.

    Validations dans l'ordre :
      1. ``LoanRequest`` n'a pas déjà un AvalisteConsent (one-to-one).
      2. ``avaliste`` ≠ ``borrower`` (un membre ne peut être son propre garant).
      3. Identification résolue (voir ``find_avaliste``).
      4. Couverture (épargne X + épargne avaliste) ≥ montant × ratio.

    L'avaliste reste *en attente*, la FK ``LoanRequest.avaliste`` n'est posée
    qu'au moment de l'acceptation (``respond_to_avaliste_consent``).
    """
    if hasattr(loan_request, "avaliste_consent"):
        existing = loan_request.avaliste_consent
        raise ValueError(
            f"LoanRequest #{loan_request.id} a déjà un consentement avaliste "
            f"(statut: {existing.statut})."
        )

    borrower = loan_request.member
    avaliste = find_avaliste(numero_identification, nom)

    if avaliste.pk == borrower.pk:
        raise ValueError("Le demandeur ne peut pas être son propre avaliste.")

    # Épargne DISPONIBLE (classique − ce qui est déjà gelé ailleurs) — évite le
    # double-nantissement d'une même épargne sur deux crédits.
    epargne_borrower = _member_available_savings(borrower)
    epargne_avaliste = _member_available_savings(avaliste)
    total_savings = epargne_borrower + epargne_avaliste
    montant = Decimal(loan_request.montant_demande)
    if montant <= 0:
        raise ValueError("Montant demandé invalide pour calcul couverture.")
    ratio_actuel = (total_savings / montant).quantize(Decimal("0.0001"))

    min_ratio = _min_coverage_ratio()
    if ratio_actuel < min_ratio:
        raise ValueError(
            f"Couverture insuffisante : {ratio_actuel} < {min_ratio} "
            f"(épargnes disponibles cumulées {total_savings} XAF / montant "
            f"{montant} XAF). Le demandeur ou l'avaliste doit augmenter son "
            f"épargne, ou baisser le montant demandé."
        )

    # Réforme garantie : l'avaliste ne comble QUE le manque. Le demandeur gèle
    # d'abord sa propre épargne dispo ; l'avaliste engage le reste.
    gel_demandeur = min(montant, epargne_borrower)
    gel_avaliste = montant - gel_demandeur  # ≤ epargne_avaliste (garanti par le ratio)

    # Garde-fou : la caution engagée ne peut dépasser l'épargne dispo de
    # l'avaliste (cohérent avec le ratio, mais on borne explicitement).
    if gel_avaliste > epargne_avaliste:
        raise ValueError(
            f"Plafond avaliste dépassé : l'avaliste devrait geler "
            f"{gel_avaliste} XAF mais ne dispose que de {epargne_avaliste} XAF "
            f"d'épargne classique libre. Demande à un autre avaliste ou baisse "
            f"le montant."
        )

    consent = AvalisteConsent.objects.create(
        loan_request=loan_request,
        avaliste=avaliste,
        statut=AvalisteConsent.Statut.PENDING,
        epargne_borrower_at_request=epargne_borrower,
        epargne_avaliste_at_request=epargne_avaliste,
        couverture_ratio=ratio_actuel,
        montant_caution=gel_avaliste,
        identification_numero_saisi=numero_identification.strip(),
        identification_nom_saisi=nom.strip(),
    )

    # Gèle la part propre du demandeur dès la soumission (collatéral engagé).
    # La caution avaliste (montant_caution) n'est comptée qu'à l'acceptation.
    loan_request.montant_gele_demandeur = gel_demandeur
    loan_request.statut = LoanRequest.Statut.EN_ATTENTE_AVALISTE
    loan_request.save(
        update_fields=["montant_gele_demandeur", "statut", "updated_at"]
    )
    # Projette le gel sur les tranches : placement d'abord, libre ensuite.
    earmark_guarantee_tranches(
        member=borrower, montant=gel_demandeur, loan_request=loan_request
    )

    record_audit(
        action="loan_request.avaliste_consent_requested",
        entite_type="LoanRequest",
        entite_id=loan_request.id,
        details={
            "avaliste_id": avaliste.id,
            "avaliste_numero": avaliste.numero_membre,
            "montant": str(montant),
            "couverture_ratio": str(ratio_actuel),
            "min_ratio": str(min_ratio),
        },
    )

    _emit("loan.avaliste_consent_requested", avaliste, consent)
    return consent


# ---------------------------------------------------------------------------
# respond_to_avaliste_consent — accept / refuse
# ---------------------------------------------------------------------------


@transaction.atomic
def respond_to_avaliste_consent(
    consent: AvalisteConsent,
    *,
    accept: bool,
    motif: str = "",
) -> AvalisteConsent:
    """Réponse explicite de l'avaliste. Idempotent + non-rétractable.

    Si ``consent`` est déjà ACCEPTED ou REFUSED, la fonction renvoie le
    consentement inchangé (sauf si on tente une rétractation après ACCEPTED →
    ``ValueError`` explicite, Q13 BUSINESS_RULES_2026).

    Effets :
      - ``ACCEPTED`` → LoanRequest.avaliste = avaliste ; statut EN_INSTRUCTION.
      - ``REFUSED`` (motif facultatif) → LoanRequest.statut = REJETEE_AVALISTE.
    """
    # Verrou pour éviter une concurrence accept/refuse.
    consent = (
        AvalisteConsent.objects.select_for_update()
        .select_related("loan_request", "avaliste")
        .get(pk=consent.pk)
    )

    if consent.statut == AvalisteConsent.Statut.ACCEPTED:
        if not accept:
            raise ValueError(
                "L'avaliste a déjà accepté ; rétractation interdite (Q13)."
            )
        return consent
    if consent.statut == AvalisteConsent.Statut.REFUSED:
        # Idempotent : on a déjà clos le dossier côté avaliste. Pas de retour
        # arrière non plus (un refus ne se "défait" pas — il faudrait une
        # nouvelle demande).
        return consent

    lr = consent.loan_request
    now = timezone.now()
    consent.responded_at = now

    if accept:
        consent.statut = AvalisteConsent.Statut.ACCEPTED
        consent.save(update_fields=["statut", "responded_at", "updated_at"])
        from .services import status_after_prevoie

        lr.avaliste = consent.avaliste
        # Après acceptation de l'avaliste, on passe par la porte « frais d'étude »
        # (en_attente) si des frais sont dus, sinon direct en instruction.
        lr.statut = status_after_prevoie(lr)
        lr.save(update_fields=["avaliste", "statut", "updated_at"])
        # La caution devient effective : on projette le gel de l'avaliste sur
        # ses tranches de placement (elles sortent du pool prêteur).
        earmark_guarantee_tranches(
            member=consent.avaliste,
            montant=consent.montant_caution,
            loan_request=lr,
        )
        record_audit(
            action="loan_request.avaliste_accepted",
            entite_type="LoanRequest",
            entite_id=lr.id,
            details={"avaliste_id": consent.avaliste_id},
        )
        _emit("loan.avaliste_consent_accepted", lr.member, consent)
    else:
        consent.statut = AvalisteConsent.Statut.REFUSED
        consent.refus_motif = (motif or "").strip()
        consent.save(
            update_fields=["statut", "responded_at", "refus_motif", "updated_at"]
        )
        lr.statut = LoanRequest.Statut.REJETEE_AVALISTE
        lr.motif_rejet = consent.refus_motif or "Refus de l'avaliste."
        lr.save(update_fields=["statut", "motif_rejet", "updated_at"])
        record_audit(
            action="loan_request.avaliste_refused",
            entite_type="LoanRequest",
            entite_id=lr.id,
            details={
                "avaliste_id": consent.avaliste_id,
                "motif": consent.refus_motif,
            },
        )
        _emit("loan.avaliste_consent_refused", lr.member, consent)

    return consent


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _emit(event_code: str, target_member: Member, consent: AvalisteConsent) -> None:
    """Émission best-effort d'un event Notification (LOT 11 mailing list)."""
    try:
        from django.conf import settings

        from apps_coop.notifications.events import emit_event

        emit_event(
            event_code,
            member=target_member,
            context={
                "prenom": target_member.prenom,
                "borrower_numero": consent.loan_request.member.numero_membre,
                "borrower_nom": consent.loan_request.member.nom,
                "montant": str(consent.loan_request.montant_demande),
                "avaliste_numero": consent.avaliste.numero_membre,
                # AUDIT-A2 . Les templates avaliste_consent_* utilisent
                # {portal_url} dans le CTA . sans cette cle, _render retombe
                # sur le corps brut (placeholders {X} litteraux).
                "portal_url": getattr(settings, "FRONTEND_PUBLIC_URL", ""),
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning("emit_event(%s) a échoué pour consent #%s", event_code, consent.id)
