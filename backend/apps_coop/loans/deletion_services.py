"""Suppression tracée d'une demande de crédit / d'un crédit (outil admin).

Le règlement admet un « escape hatch » : l'administration peut SUPPRIMER une
demande de crédit erronée (et le crédit associé s'il existe). Toute suppression
est **tracée dans un fichier .txt** persistant (``MEDIA_ROOT/audit/
suppressions_credit.txt``, monté en volume en prod) EN PLUS de l'AuditLog.

Garde-fou intégrité : un crédit adossé à un **financement prêteur**
(allocations / funding) ou à une **procédure contentieuse** n'est PAS
supprimable — ces objets engagent des tiers et du ledger ; on invalide plutôt
les paiements (cf. ``payments.services.invalidate_payment``).
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import LoanRequest


logger = logging.getLogger(__name__)


class LoanDeletionError(ValueError):
    """Suppression impossible (motif lisible)."""


def _trace_path() -> Path:
    base = Path(settings.MEDIA_ROOT) / "audit"
    base.mkdir(parents=True, exist_ok=True)
    return base / "suppressions_credit.txt"


def _append_trace(line: str) -> None:
    try:
        with open(_trace_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        # Ne jamais bloquer la suppression sur l'écriture de la trace fichier :
        # l'AuditLog DB reste la source de vérité. On loggue l'échec.
        logger.exception("Impossible d'écrire la trace de suppression crédit")


@transaction.atomic
def delete_loan_request_traced(loan_request: LoanRequest, *, actor, motif: str = "") -> dict:
    """Supprime ``loan_request`` (et son ``Loan`` éventuel), avec trace.

    Renvoie un récapitulatif (dict) de ce qui a été supprimé. Lève
    ``LoanDeletionError`` si le crédit est trop engagé pour être supprimé.
    """
    from apps_coop.payments.models import Payment

    from .guarantee_tranches import release_guarantee_tranches

    member = loan_request.member
    loan = getattr(loan_request, "loan", None)

    if loan is not None:
        # Garde-fou : un crédit financé par des prêteurs ou en procédure ne
        # peut pas être détruit sans casser le ledger tiers.
        if loan.lender_allocations.exists() or hasattr(loan, "funding_request"):
            raise LoanDeletionError(
                "Ce crédit a un financement prêteur : suppression bloquée. "
                "Invalidez les paiements concernés plutôt que de supprimer."
            )
        if hasattr(loan, "judicial_escalation"):
            raise LoanDeletionError(
                "Ce crédit est en procédure contentieuse : suppression bloquée."
            )

    # Récap AVANT suppression (pour la trace).
    recap = {
        "loan_request_id": loan_request.id,
        "loan_id": getattr(loan, "id", None),
        "numero_dossier": getattr(loan, "numero_dossier", None),
        "member": f"{member.numero_membre} · {member.nom} {member.prenom}".strip(),
        "montant_demande": str(loan_request.montant_demande),
        "statut": loan_request.statut,
        "motif": (motif or "").strip(),
    }

    # Libère les gels (SET_NULL de toute façon, mais on nettoie l'état).
    release_guarantee_tranches(loan_request)

    if loan is not None:
        # Détache/supprime les dépendances PROTECT du Loan.
        Payment.objects.filter(loan=loan).update(loan=None, loan_installment=None)
        loan.renewals.all().delete()
        for inst in loan.installments.all():
            inst.repayments.all().delete()
        loan.delete()  # cascade installments + guarantees

    loan_request.delete()

    # Trace fichier (best-effort) + AuditLog (source de vérité).
    ts = timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z")
    actor_label = getattr(actor, "username", None) or getattr(actor, "email", None) or "?"
    _append_trace(
        f"[{ts}] SUPPRESSION par {actor_label} — "
        f"LR#{recap['loan_request_id']} / Loan#{recap['loan_id']} "
        f"({recap['numero_dossier']}) — membre {recap['member']} — "
        f"montant {recap['montant_demande']} — statut {recap['statut']}"
        + (f" — motif: {recap['motif']}" if recap["motif"] else "")
    )
    record_audit(
        action="loan_request.deleted",
        entite_type="LoanRequest",
        entite_id=recap["loan_request_id"],
        user=actor,
        details=recap,
    )
    return recap
