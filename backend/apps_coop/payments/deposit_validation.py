"""Règles de validation des VERSEMENTS (collecte + épargne classique).

Source unique partagée par les deux canaux qui créent un dépôt :

  * membre self-service — ``init_payment`` (``POST /payments/init/``) ;
  * versement manuel agence — ``admin_cash_in_payment``
    (``POST /payments/admin/cash-in/``).

Avant ce module, la validation ne vivait que dans ``init_payment`` : le cash-in
admin créait des dépôts SANS aucune règle (plancher 1 000, gate ``config.actif``,
plafond, pas de 50 sur la collecte, fenêtre placement). Un admin pouvait donc
enregistrer un dépôt classique produit fermé / sous le minimum / au-dessus du
plafond, ou marquer un ``is_placement`` hors fenêtre (écriture « placement »
sans tranche prêteur → argent non bloqué mais annoncé comme placé). Factoriser
ici garantit que **les deux canaux appliquent exactement les mêmes règles**.

Chaque helper lève ``DepositValidationError`` (message prêt à servir de
``detail`` HTTP 400) ; sinon retourne ``None``.
"""
from __future__ import annotations


class DepositValidationError(Exception):
    """Règle de versement violée — ``str(exc)`` = message pour Response detail."""


def validate_collecte_deposit(*, montant, nb_jours: int, allow_any_amount: bool = False) -> None:
    """Collecte journalière : plafond multi-jours, pas de 50, minimum/jour."""
    from apps_coop.audit.services import get_int_setting

    min_per_day = get_int_setting("collecte.min_per_day", 1000)
    max_days = get_int_setting("collecte.prepay.max_days", 30)
    # Pas du montant : la collecte se verse par multiples de 50 FCFA (tunable).
    step = get_int_setting("collecte.amount_step", 50)

    if nb_jours > max_days:
        raise DepositValidationError(
            f"Mode multi-jours plafonné à {max_days} jours (reçu {nb_jours})."
        )
    if not allow_any_amount and step > 0 and montant % step != 0:
        raise DepositValidationError(
            f"Le montant de la collecte doit être un multiple de {step} FCFA "
            f"(reçu {int(montant)})."
        )
    # Minimum min_per_day PAR JOUR → total ≥ nb_jours × min_per_day.
    min_total = nb_jours * min_per_day
    if not allow_any_amount and montant < min_total:
        label = (
            f"Mode multi-jours : montant minimum {nb_jours} × {min_per_day} "
            f"= {min_total} FCFA"
            if nb_jours > 1
            else f"Montant minimum de la collecte : {min_per_day} FCFA par jour"
        )
        raise DepositValidationError(f"{label} (reçu {int(montant)}).")


def validate_classique_deposit(*, montant, allow_any_amount: bool = False) -> None:
    """Épargne classique : gate ``config.actif``, plancher 1 000, plafond."""
    from apps_coop.savings.models import ClassicSavingsConfig

    cfg = ClassicSavingsConfig.get_solo()
    if not cfg.actif:
        raise DepositValidationError(
            "L'épargne classique n'est pas ouverte aux dépôts pour le moment."
        )
    # Plancher réglementaire : tout versement a un minimum de 1 000 XAF. La config
    # admin ``depot_min`` ne peut que le RELEVER, jamais l'abaisser sous 1 000.
    min_deposit = max(int(cfg.depot_min or 0), 1000)
    if not allow_any_amount and montant < min_deposit:
        raise DepositValidationError(f"Dépôt minimum : {min_deposit} XAF.")
    if not allow_any_amount and cfg.depot_max is not None and montant > cfg.depot_max:
        raise DepositValidationError(f"Dépôt maximum : {int(cfg.depot_max)} XAF.")


def ensure_savings_carnet(member) -> None:
    """Épargne / collecte journalière : le membre doit posséder un carnet
    ``collecte`` avant tout versement.

    Décision 2026-08 (cohérence rapports/audit) : « une écriture ne se fait que
    dans un carnet ». Le blocage était déjà en place pour tontine/caisse (chacun
    son carnet) ; on l'étend ici à la collecte/épargne classique, qui partagent
    le carnet ``collecte`` (acquis normalement aux frais d'activation). Un membre
    sans carnet collecte (ex. créé manuellement) doit d'abord s'en voir vendre
    un — l'agence peut le faire au comptant (``FRAIS_CARNET``).
    """
    from apps_coop.members.models import BookletOrder

    if BookletOrder.latest_for(member, BookletOrder.Type.COLLECTE) is None:
        raise DepositValidationError(
            "Aucun carnet collecte : le membre doit d'abord posséder un carnet "
            "avant tout versement (épargne / collecte). Vends-lui un carnet, "
            "puis réessaie."
        )


def validate_placement_window(member) -> None:
    """Placement : ouvert seulement pendant les N premiers mois d'ancienneté.

    Barrière serveur commune : le client masque déjà l'option, mais le cash-in
    admin n'avait aucune garde → un ``is_placement`` hors fenêtre créait une
    écriture « placement » sans tranche (argent non gelé). On refuse ici.
    """
    from apps_coop.savings.placement import (
        placement_eligibility_months,
        placement_open_for_member,
    )

    if not placement_open_for_member(member):
        months = placement_eligibility_months()
        raise DepositValidationError(
            f"Le placement n'est ouvert que pendant les {months} premiers mois "
            f"suivant l'adhésion. L'épargne peut toujours être versée en LIBRE."
        )
