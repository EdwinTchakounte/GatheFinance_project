"""Service-layer functions for the savings withdrawal flow.

Politique (cf. WithdrawalRequest) : le membre demande un retrait, l'admin
valide. À l'approbation, le solde est débité via une SavingsTransaction
`retrait`. Atomique + idempotent.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import SavingsAccount, SavingsTransaction, WithdrawalRequest


logger = logging.getLogger(__name__)


@transaction.atomic
def request_withdrawal(account: SavingsAccount, *, montant: Decimal, motif: str = "") -> WithdrawalRequest:
    """Crée une `WithdrawalRequest(en_attente)`.

    Règles :
      - montant strictement positif
      - montant ≤ solde disponible (verrou ligne pour éviter une demande
        au-dessus du solde en cas de mouvements concurrents)
      - pas de demande déjà `en_attente` pour ce compte (un retrait à la fois)
    """
    montant = Decimal(montant)
    if montant <= 0:
        raise ValueError("Le montant du retrait doit être positif.")

    locked = SavingsAccount.objects.select_for_update().get(pk=account.pk)
    if montant > Decimal(locked.solde):
        raise ValueError(
            f"Montant demandé ({montant}) supérieur au solde disponible "
            f"({locked.solde})."
        )

    existing = (
        WithdrawalRequest.objects.select_for_update()
        .filter(account=locked, statut=WithdrawalRequest.Statut.EN_ATTENTE)
        .first()
    )
    if existing:
        raise ValueError(
            "Une demande de retrait est déjà en attente. Attends la décision "
            "de l'administration avant d'en soumettre une nouvelle."
        )

    wr = WithdrawalRequest.objects.create(
        account=locked,
        montant=montant,
        motif=(motif or "").strip(),
    )
    record_audit(
        action="withdrawal.requested",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=locked.member.user,
        details={
            "member_id": locked.member_id,
            "montant": str(montant),
            "solde": str(locked.solde),
        },
    )
    return wr


@transaction.atomic
def decide_withdrawal(
    wr: WithdrawalRequest,
    *,
    decided_by,
    approve: bool,
    motif_rejet: str = "",
) -> WithdrawalRequest:
    """Approuve (débite le solde) ou rejette une demande de retrait.

    Idempotent : si déjà décidée, renvoie la demande telle quelle.
    À l'approbation : revérifie le solde sous verrou, crée la SavingsTransaction
    `retrait`, met à jour le solde, lie la transaction à la demande.
    """
    if wr.statut != WithdrawalRequest.Statut.EN_ATTENTE:
        return wr  # déjà traitée — idempotent

    now = timezone.now()

    if not approve:
        motif_rejet = (motif_rejet or "").strip()
        if not motif_rejet:
            raise ValueError("Un motif de rejet est requis.")
        wr.statut = WithdrawalRequest.Statut.REJETEE
        wr.motif_rejet = motif_rejet
        wr.decide_par = decided_by
        wr.date_decision = now
        wr.save(update_fields=["statut", "motif_rejet", "decide_par", "date_decision", "updated_at"])
        record_audit(
            action="withdrawal.rejected",
            entite_type="WithdrawalRequest",
            entite_id=wr.id,
            user=decided_by,
            details={"motif": motif_rejet},
        )
        _notify(wr, approved=False)
        return wr

    # --- Approbation : débit du solde, sous verrou ---
    account = SavingsAccount.objects.select_for_update().get(pk=wr.account_id)
    montant = Decimal(wr.montant)
    if montant > Decimal(account.solde):
        raise ValueError(
            f"Solde insuffisant pour approuver : {account.solde} < {montant}."
        )

    nouveau_solde = Decimal(account.solde) - montant
    account.solde = nouveau_solde
    account.save(update_fields=["solde", "updated_at"])

    tx = SavingsTransaction.objects.create(
        account=account,
        payment=None,  # mouvement interne, pas un Payment entrant
        type_op=SavingsTransaction.TypeOp.RETRAIT,
        montant=montant,
        solde_apres=nouveau_solde,
        date=now,
    )

    wr.statut = WithdrawalRequest.Statut.APPROUVEE
    wr.transaction = tx
    wr.decide_par = decided_by
    wr.date_decision = now
    wr.save(update_fields=["statut", "transaction", "decide_par", "date_decision", "updated_at"])

    record_audit(
        action="withdrawal.approved",
        entite_type="WithdrawalRequest",
        entite_id=wr.id,
        user=decided_by,
        details={
            "montant": str(montant),
            "solde_apres": str(nouveau_solde),
            "transaction_id": tx.id,
        },
    )
    _notify(wr, approved=True)
    return wr


def _notify(wr: WithdrawalRequest, *, approved: bool) -> None:
    """Email + notif in-app au membre (best-effort, ne casse jamais le flow)."""
    from django.conf import settings as dj_settings

    from apps_coop.notifications.services import send_template

    member = wr.account.member
    if not getattr(member.user, "email", None):
        return
    code = "withdrawal.approved" if approved else "withdrawal.rejected"
    try:
        send_template(
            code,
            to=member.user.email,
            member=member,
            context={
                "prenom": member.prenom,
                "montant": f"{int(wr.montant):,}".replace(",", " "),
                "motif_rejet": wr.motif_rejet,
                "portal_url": getattr(dj_settings, "FRONTEND_BASE_URL", "http://localhost:3200"),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("withdrawal notification failed for %s", code, exc_info=True)
