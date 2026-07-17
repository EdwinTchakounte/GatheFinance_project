"""Libération automatique des tranches gelées en garantie (réforme 2026).

Le gel de garantie est **dérivé** partout ailleurs : ``member_frozen_guarantee``
recalcule le montant à la volée en filtrant sur les statuts, il n'y a donc
aucun point de libération explicite dans le code métier. Or les tranches
``GELEE`` (voir ``guarantee_tranches``), elles, portent un état persisté : il
faut bien les rendre au pool quand le gel tombe.

Plutôt que d'aller greffer un appel dans chacune des transitions de statut
dispersées (vues membre, écrans admin, tâches de clôture), on écoute le statut
lui-même — exactement la même règle que celle qu'applique le calcul dérivé :

  * ``LoanRequest`` rejetée (REJETEE / REJETEE_AVALISTE / REJETEE_CAMPAGNE)
  * ``Loan`` CLOTURE (crédit soldé)

La libération est idempotente, donc un ``post_save`` répété est sans effet.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .guarantee_tranches import release_guarantee_tranches
from .models import Loan, LoanRequest


logger = logging.getLogger(__name__)


@receiver(post_save, sender=LoanRequest, dispatch_uid="release_guarantee_on_request_rejected")
def _release_on_request_rejected(sender, instance: LoanRequest, **kwargs) -> None:
    from .avaliste_services import _released_request_statuses

    if instance.statut in _released_request_statuses():
        release_guarantee_tranches(instance)


@receiver(post_save, sender=Loan, dispatch_uid="release_guarantee_on_loan_closed")
def _release_on_loan_closed(sender, instance: Loan, **kwargs) -> None:
    if instance.statut != Loan.Statut.CLOTURE:
        return
    if instance.loan_request_id is None:
        return
    release_guarantee_tranches(instance.loan_request)
