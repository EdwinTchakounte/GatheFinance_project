"""Apport coop — restitution ANTICIPÉE d'un placement prêteur (2026-07).

Contexte : le placement d'un prêteur peut financer plusieurs crédits, remboursés
à des dates différentes. Si un crédit financé n'est pas encore remboursé alors
que le prêteur doit être restitué « à terme », l'admin peut faire un **apport** :
la coop **reprend le risque** du crédit, restitue intégralement le prêteur
(capital libéré + intérêts placement au prorata), et **garde pour elle** la
part d'intérêts de ce prêteur sur les remboursements futurs.

Effets d'une restitution par apport d'une tranche ENGAGÉE :
  1. Intérêts placement à **taux fixe** (capital × taux placement), calculés et
     crédités au clic sur « Restituer » (décision 2026-07-22 : plus de prorata
     jours, qui tombait à 0 juste après l'engagement).
  2. Tranche ENGAGÉE → LIBÉRÉE : le capital (qui vit dans le solde classique du
     prêteur, la tranche n'étant qu'un verrou) redevient retirable. Une ligne
     ``RESTITUTION_PLACEMENT`` INFORMATIVE (solde inchangé) le trace au relevé.
  3. ``LenderAllocation.restitue_par_apport = True`` : le prêteur est exclu de la
     distribution d'intérêts des remboursements futurs (la coop garde sa part).
  4. Le crédit reste dû par le membre (statut inchangé) : le recouvrement
     continue au profit de la coop.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.portal_urls import portal_url


class ApportError(ValueError):
    """Restitution par apport impossible (message lisible pour l'admin)."""


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def restitute_tranche_by_apport(tranche_id: int, *, admin_user=None) -> dict:
    """Restitue par apport une tranche ENGAGÉE. Renvoie un récap.

    Lève ``ApportError`` si la tranche n'est pas ENGAGÉE, si le crédit est déjà
    soldé (restitution normale, pas d'apport), ou si le prêteur n'a pas de
    compte d'épargne classique.
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        LenderTranche,
    )
    from apps_coop.savings.placement_maturity import placement_interest_rate

    from .models import LenderAllocation, Loan

    # NB : on ne `select_related` PAS `engaged_in_loan` (FK nullable) dans la
    # requête verrouillée — sous PostgreSQL, `FOR UPDATE` ne peut pas porter sur
    # le côté nullable d'un OUTER JOIN. `member` (non-null) est joint sans souci ;
    # le loan se charge à part.
    tranche = (
        LenderTranche.objects.select_for_update()
        .select_related("member")
        .get(pk=tranche_id)
    )
    if tranche.statut != LenderTranche.Statut.ENGAGEE:
        raise ApportError(
            "Seule une tranche ENGAGÉE (finançant un crédit en cours) peut être "
            "restituée par apport."
        )
    loan = tranche.engaged_in_loan
    if loan is not None and loan.statut == Loan.Statut.CLOTURE:
        raise ApportError(
            "Le crédit financé est déjà soldé — la tranche se libère normalement, "
            "aucun apport nécessaire."
        )

    account = (
        ClassicSavingsAccount.objects.select_for_update()
        .filter(member=tranche.member)
        .first()
    )
    if account is None:
        raise ApportError("Le prêteur n'a pas de compte d'épargne classique.")

    now = timezone.now()

    # 1) Intérêts placement — TAUX FIXE appliqué au clic sur « Restituer »
    #    (décision 2026-07-22). Plus de prorata jours : le prorata tombait à 0
    #    dès qu'on restituait peu après l'engagement (jours ≈ 0 → intérêt = 0,
    #    aucun crédit écrit). Désormais : intérêt = capital × taux_placement,
    #    calculé et crédité immédiatement à la restitution.
    rate = placement_interest_rate()
    interest = _q(Decimal(tranche.montant) * rate)
    if interest > 0:
        nouveau_solde = _q(Decimal(account.solde) + interest)
        ClassicSavingsTransaction.objects.create(
            account=account,
            payment=None,
            type_op=ClassicSavingsTransaction.TypeOp.INTERET_PLACEMENT,
            montant=interest,
            solde_apres=nouveau_solde,
            date=now,
        )
        account.solde = nouveau_solde
        account.save(update_fields=["solde", "updated_at"])

    # 2) Libère la tranche (capital de nouveau retirable).
    tranche.statut = LenderTranche.Statut.LIBEREE
    tranche.released_at = now
    tranche.save(update_fields=["statut", "released_at", "updated_at"])

    # 2bis) Trace le CAPITAL restitué sur le relevé (décision 2026-07-22). Ligne
    #    INFORMATIVE : le capital vit déjà dans le solde (la tranche n'était
    #    qu'un verrou), on ne le RE-crédite donc PAS — ``solde_apres`` reste le
    #    solde courant (inchangé par le capital). Elle rend juste visible pour le
    #    prêteur que son capital de placement lui a été restitué (débloqué).
    ClassicSavingsTransaction.objects.create(
        account=account,
        payment=None,
        type_op=ClassicSavingsTransaction.TypeOp.RESTITUTION_PLACEMENT,
        montant=_q(Decimal(tranche.montant)),
        solde_apres=_q(Decimal(account.solde)),
        date=now,
    )

    # 3) La coop reprend le risque → exclut ce prêteur des intérêts futurs.
    if loan is not None:
        LenderAllocation.objects.filter(loan=loan, tranche=tranche).update(
            restitue_par_apport=True
        )

    record_audit(
        action="lender.apport_restitution",
        entite_type="LenderTranche",
        entite_id=tranche.id,
        user=admin_user,
        details={
            "member_id": tranche.member_id,
            "loan_id": getattr(loan, "id", None),
            "capital": str(tranche.montant),
            "interet_placement": str(interest),
        },
    )

    member = tranche.member
    dossier = getattr(loan, "numero_dossier", "")

    def _notify() -> None:
        try:
            from django.conf import settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "lender.apport_restitution",
                member=member,
                context={
                    "prenom": member.prenom,
                    "capital": f"{int(Decimal(tranche.montant)):,}".replace(",", " "),
                    "interet": f"{int(interest):,}".replace(",", " "),
                    "numero_dossier": dossier,
                    "portal_url": portal_url(),
                },
            )
        except Exception:  # pragma: no cover — best-effort
            pass

    transaction.on_commit(_notify)

    return {
        "tranche_id": tranche.id,
        "capital": str(tranche.montant),
        "interet_placement": str(interest),
        "loan_id": getattr(loan, "id", None),
    }
