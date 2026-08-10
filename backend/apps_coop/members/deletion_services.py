"""Suppression tracée d'un membre (outil admin, cascade complète).

Supprime DÉFINITIVEMENT un membre et toutes ses données — compte auth, épargne
(collecte / classique / placement), crédits & demandes, paiements, carnets,
documents, notifications, support — dans l'ordre des dépendances (plusieurs FK
sont en PROTECT, donc l'ordre compte). IRRÉVERSIBLE.

Garde-fou intégrité tiers : un membre engagé sur le crédit d'un AUTRE membre
(prêteur avec une allocation sur un crédit non clôturé, ou avaliste d'un crédit
non clôturé) n'est PAS supprimable — sa suppression casserait le dossier du
tiers. On lève alors ``MemberDeletionError`` (→ 409).

Toute suppression est tracée : fichier ``MEDIA_ROOT/audit/suppressions_membres.txt``
(best-effort, monté en volume en prod) EN PLUS de l'AuditLog (source de vérité).
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import Member


logger = logging.getLogger(__name__)


class MemberDeletionError(ValueError):
    """Suppression impossible (motif lisible → 409)."""


def _trace_path() -> Path:
    base = Path(settings.MEDIA_ROOT) / "audit"
    base.mkdir(parents=True, exist_ok=True)
    return base / "suppressions_membres.txt"


def _append_trace(line: str) -> None:
    try:
        with open(_trace_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        # Ne jamais bloquer la suppression sur l'écriture de la trace fichier :
        # l'AuditLog DB reste la source de vérité.
        logger.exception("Impossible d'écrire la trace de suppression membre")


def third_party_engagements(member: Member) -> list[str]:
    """Raisons pour lesquelles supprimer ``member`` casserait un tiers.

    Renvoie une liste (vide = suppression sûre). Utilisé aussi côté API pour
    prévenir l'admin AVANT la confirmation.
    """
    from apps_coop.loans.models import AvalisteConsent, LenderAllocation, Loan

    reasons: list[str] = []

    # Prêteur : allocation sur le crédit d'autrui, non clôturé.
    if (
        LenderAllocation.objects.filter(lender=member)
        .exclude(loan__member=member)
        .exclude(loan__statut=Loan.Statut.CLOTURE)
        .exists()
    ):
        reasons.append("prêteur d'un crédit en cours (allocation active)")

    # Avaliste : garant d'un crédit d'autrui non clôturé (ou demande encore ouverte).
    aval_qs = AvalisteConsent.objects.filter(avaliste=member).exclude(
        loan_request__member=member
    ).select_related("loan_request__loan")
    for consent in aval_qs:
        loan = getattr(consent.loan_request, "loan", None)
        if loan is None or loan.statut != Loan.Statut.CLOTURE:
            reasons.append("avaliste d'un crédit non clôturé")
            break

    return reasons


@transaction.atomic
def delete_member_cascade(member: Member, *, actor, motif: str = "") -> dict:
    """Supprime définitivement ``member`` et TOUTES ses données (cascade).

    Lève ``MemberDeletionError`` (409) si le membre est engagé sur le crédit
    d'un tiers (prêteur/avaliste actif). Renvoie un récap (dict) de ce qui a été
    supprimé.
    """
    from apps_coop.loans.models import (
        AvalisteConsent,
        JudicialEscalation,
        LenderConsentRequest,
        Loan,
        LoanFundingRequest,
        LoanInstallment,
        LoanRequest,
    )
    from apps_coop.payments.models import Payment
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        LenderConsent,
        LenderTranche,
        SavingsAccount,
        SavingsTransaction,
    )

    from .models import BRCDocument, BookletOrder

    reasons = third_party_engagements(member)
    if reasons:
        raise MemberDeletionError(
            "Suppression bloquée : ce membre est "
            + " ; ".join(reasons)
            + ". Clôturez ou transférez ces engagements avant de le supprimer."
        )

    user = member.user
    # Récap AVANT suppression (pour la trace + la réponse API).
    recap = {
        "member_id": member.id,
        "numero_membre": member.numero_membre,
        "member": member.nom_complet,
        "email": (getattr(user, "email", "") or ""),
        "statut": member.statut,
        "motif": (motif or "").strip(),
    }

    # 1. Paiements (PROTECT sur `member` ET sur `loan`) — à supprimer en premier.
    Payment.objects.filter(member=member).delete()
    Payment.objects.filter(loan__member=member).delete()

    # 2. Crédits + dépendances descendantes (installments, funding, contentieux).
    for loan in Loan.objects.filter(member=member):
        JudicialEscalation.objects.filter(loan=loan).delete()
        LoanInstallment.objects.filter(loan=loan).delete()
        LoanFundingRequest.objects.filter(loan=loan).delete()
        loan.delete()

    # 3. Demandes + consentements avaliste / prêteur PROPRES au membre.
    AvalisteConsent.objects.filter(avaliste=member).delete()
    AvalisteConsent.objects.filter(loan_request__member=member).delete()
    LenderConsentRequest.objects.filter(lender=member).delete()
    LoanRequest.objects.filter(member=member).delete()

    # 4. Carnets + justificatifs BRC (PROTECT).
    BRCDocument.objects.filter(member=member).delete()
    BookletOrder.objects.filter(member=member).delete()

    # 5. Épargne : tranches/consentement prêteur (PROTECT) puis comptes.
    LenderTranche.objects.filter(member=member).delete()
    LenderConsent.objects.filter(member=member).delete()
    ClassicSavingsAccount.objects.filter(member=member).delete()
    SavingsTransaction.objects.filter(account__member=member).delete()
    SavingsAccount.objects.filter(member=member).delete()

    # 6. Le membre (cascade documents / support / …) puis son compte auth
    #    (cascade notifications / tokens / réactions / commentaires ;
    #    les champs d'audit passent en SET_NULL et survivent).
    member.delete()
    if user is not None:
        user.delete()

    # Trace fichier (best-effort) + AuditLog (source de vérité).
    ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    actor_label = (
        getattr(actor, "username", None) or getattr(actor, "email", None) or "?"
    )
    _append_trace(
        f"[{ts}] SUPPRESSION MEMBRE par {actor_label} — "
        f"#{recap['member_id']} {recap['numero_membre']} · {recap['member']} "
        f"({recap['email']}) — statut {recap['statut']}"
        + (f" — motif: {recap['motif']}" if recap["motif"] else "")
    )
    record_audit(
        action="member.deleted",
        entite_type="Member",
        entite_id=recap["member_id"],
        user=actor,
        details=recap,
    )
    return recap
