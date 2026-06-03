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
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import (
    get_str_setting,
    record as record_audit,
)
from apps_coop.members.models import Member

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


def _member_total_savings(member: Member) -> Decimal:
    """Somme des soldes collecte + classique du membre (refonte 2026).

    Renvoie 0 si aucun compte n'a encore été créé. Ne lève jamais — utilisée
    en lecture pour la couverture avaliste, pas pour un débit.
    """
    total = Decimal("0")
    try:
        # Collecte journalière (SavingsAccount).
        from apps_coop.savings.models import SavingsAccount  # local

        sa = SavingsAccount.objects.filter(member=member).first()
        if sa is not None:
            total += Decimal(sa.solde)
    except Exception:  # noqa: BLE001 — tables not migrated / missing
        pass
    try:
        # Épargne classique.
        if hasattr(member, "classic_savings_account"):
            total += Decimal(member.classic_savings_account.solde)
    except Exception:  # noqa: BLE001
        pass
    return total


# ---------------------------------------------------------------------------
# Identification — find_avaliste
# ---------------------------------------------------------------------------


def find_avaliste(numero_identification: str, nom: str) -> Member:
    """Résout l'avaliste par double-clé numéro + nom.

    Lève :
      - ``LookupError`` si le numéro est inconnu.
      - ``ValueError`` si le nom ne correspond pas, le membre n'est pas
        ACTIF, ou n'est pas senior.

    Validation casse-insensible + trim sur ``nom`` (anti-faute de frappe).
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

    if not avaliste.is_senior:
        raise ValueError(
            f"Le membre {numero} n'a pas l'ancienneté requise pour être avaliste."
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

    epargne_borrower = _member_total_savings(borrower)
    epargne_avaliste = _member_total_savings(avaliste)
    total_savings = epargne_borrower + epargne_avaliste
    montant = Decimal(loan_request.montant_demande)
    if montant <= 0:
        raise ValueError("Montant demandé invalide pour calcul couverture.")
    ratio_actuel = (total_savings / montant).quantize(Decimal("0.0001"))

    min_ratio = _min_coverage_ratio()
    if ratio_actuel < min_ratio:
        raise ValueError(
            f"Couverture insuffisante : {ratio_actuel} < {min_ratio} "
            f"(épargnes cumulées {total_savings} XAF / montant {montant} XAF). "
            f"Le demandeur ou l'avaliste doit augmenter son épargne."
        )

    consent = AvalisteConsent.objects.create(
        loan_request=loan_request,
        avaliste=avaliste,
        statut=AvalisteConsent.Statut.PENDING,
        epargne_borrower_at_request=epargne_borrower,
        epargne_avaliste_at_request=epargne_avaliste,
        couverture_ratio=ratio_actuel,
        identification_numero_saisi=numero_identification.strip(),
        identification_nom_saisi=nom.strip(),
    )

    loan_request.statut = LoanRequest.Statut.EN_ATTENTE_AVALISTE
    loan_request.save(update_fields=["statut", "updated_at"])

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
        lr.avaliste = consent.avaliste
        lr.statut = LoanRequest.Statut.EN_INSTRUCTION
        lr.save(update_fields=["avaliste", "statut", "updated_at"])
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
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning("emit_event(%s) a échoué pour consent #%s", event_code, consent.id)
