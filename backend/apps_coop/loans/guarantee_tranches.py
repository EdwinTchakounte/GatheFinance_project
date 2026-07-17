"""Matérialisation du gel de garantie sur les tranches de placement.

Réforme garantie 2026 — deuxième temps.

Le gel de garantie (collatéral du demandeur + caution de l'avaliste) était
jusqu'ici un simple **montant** posé sur la ``LoanRequest`` / l'
``AvalisteConsent``. Conséquence : une épargne gelée en garantie restait
sélectionnable dans le pool prêteur — le même argent pouvait garantir un crédit
**et** en financer un autre.

Ce module ferme ce trou en marquant **quelles tranches** sont gelées :

  * ``earmark_guarantee_tranches`` — puise d'abord dans le **placement**
    (tranches ``DISPONIBLE``), puis laisse le reliquat sur la part **libre**.
    Les tranches retenues passent ``DISPONIBLE`` → ``GELEE`` et sortent donc du
    pool (toutes les requêtes de funding filtrent sur ``DISPONIBLE``).
  * ``release_guarantee_tranches`` — retour ``GELEE`` → ``DISPONIBLE`` au rejet
    de la demande ou à la clôture du crédit garanti.

Le **montant** du gel reste la source de vérité pour le calcul du retirable
(``classic_withdrawable``) et de la capacité de caution : les tranches ne sont
qu'une projection de ce montant sur la partie placement. Un gel dont le
placement est insuffisant est donc parfaitement valide — il mord simplement sur
la part libre, qui n'est pas tranchée.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

from apps_coop.savings.models import LenderTranche


logger = logging.getLogger(__name__)


def earmark_guarantee_tranches(*, member, montant, loan_request) -> Decimal:
    """Gèle jusqu'à ``montant`` XAF de placement DISPONIBLE de ``member``.

    Les tranches sont prises de la plus ancienne à la plus récente. Si la
    dernière tranche retenue dépasse le besoin restant, elle est **splittée** :
    la part nécessaire passe ``GELEE``, le reliquat reste ``DISPONIBLE`` dans
    une nouvelle tranche (même convention que le split du funding manuel).

    Renvoie le montant réellement gelé **sur le placement**. Le reliquat
    (``montant`` − retour) est couvert par la part libre, sans matérialisation.

    À appeler dans une transaction (les appelants sont tous ``@transaction.atomic``).
    """
    besoin = Decimal(montant or 0)
    if besoin <= 0:
        return Decimal("0")

    now = timezone.now()
    tranches = (
        LenderTranche.objects.select_for_update()
        .filter(member=member, statut=LenderTranche.Statut.DISPONIBLE)
        .order_by("created_at", "id")
    )

    gele = Decimal("0")
    for t in tranches:
        restant = besoin - gele
        if restant <= 0:
            break
        montant_t = Decimal(t.montant)
        if montant_t > restant:
            # Split : on ne gèle que ce dont on a besoin, le surplus retourne
            # au pool sous forme d'une nouvelle tranche DISPONIBLE.
            LenderTranche.objects.create(
                member=member,
                montant=montant_t - restant,
                statut=LenderTranche.Statut.DISPONIBLE,
            )
            t.montant = restant
        t.statut = LenderTranche.Statut.GELEE
        t.gele_par_loan_request = loan_request
        t.gele_at = now
        t.save(
            update_fields=[
                "montant",
                "statut",
                "gele_par_loan_request",
                "gele_at",
                "updated_at",
            ]
        )
        gele += Decimal(t.montant)

    return gele


def release_guarantee_tranches(loan_request) -> int:
    """Rend au pool les tranches gelées par ``loan_request``. Idempotent.

    Renvoie le nombre de tranches libérées. Une tranche déjà ``ENGAGEE`` n'est
    jamais touchée : le gel a beau tomber, l'argent finance un crédit vivant et
    seul le funding décide de la libérer.
    """
    if loan_request is None or loan_request.pk is None:
        return 0
    return (
        LenderTranche.objects.filter(
            gele_par_loan_request=loan_request,
            statut=LenderTranche.Statut.GELEE,
        ).update(
            statut=LenderTranche.Statut.DISPONIBLE,
            gele_par_loan_request=None,
            gele_at=None,
            updated_at=timezone.now(),
        )
    )
