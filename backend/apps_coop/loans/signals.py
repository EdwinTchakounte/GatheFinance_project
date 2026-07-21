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

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .guarantee_tranches import release_guarantee_tranches
from .lender_payouts import release_loan_tranches
from .models import Loan, LoanRequest


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification STAFF : un dossier crédit devient prêt pour le comité
# (transition → EN_INSTRUCTION), toutes voies confondues (garantie, avaliste
# accepté, auto-couverture). On capture l'ancien statut en pre_save puis on
# notifie une seule fois sur la vraie transition — pas de spam sur les re-save.
# ---------------------------------------------------------------------------
@receiver(pre_save, sender=LoanRequest, dispatch_uid="capture_old_statut_for_staff_notif")
def _capture_old_statut(sender, instance: LoanRequest, **kwargs) -> None:
    if instance.pk:
        instance._old_statut = (
            LoanRequest.objects.filter(pk=instance.pk)
            .values_list("statut", flat=True)
            .first()
        )
    else:
        instance._old_statut = None


@receiver(post_save, sender=LoanRequest, dispatch_uid="notify_staff_credit_ready")
def _notify_staff_on_instruction(sender, instance: LoanRequest, **kwargs) -> None:
    old = getattr(instance, "_old_statut", None)
    if (
        instance.statut == LoanRequest.Statut.EN_INSTRUCTION
        and old != LoanRequest.Statut.EN_INSTRUCTION
    ):
        _notify_staff_credit_ready(instance)


def _notify_staff_credit_ready(loan_request) -> None:
    """Envoie un e-mail à l'équipe (adresse ops configurable) : un dossier crédit
    est prêt pour le comité. No-op si ``notifications.ops_email`` n'est pas
    renseigné. Best-effort, après commit.
    """
    from django.db import transaction

    try:
        from apps_coop.audit.services import get_str_setting

        ops = (get_str_setting("notifications.ops_email", "") or "").strip()
    except Exception:  # pragma: no cover
        ops = ""
    if not ops:
        return

    from django.conf import settings

    member = loan_request.member
    # {admin_url} du CTA : AppSetting dédié sinon repli sur l'URL front publique.
    admin_url = ""
    try:
        admin_url = (get_str_setting("notifications.admin_url", "") or "").strip()
    except Exception:  # pragma: no cover
        admin_url = ""
    if not admin_url:
        admin_url = getattr(settings, "FRONTEND_PUBLIC_URL", "")
    ctx = {
        "prenom": member.prenom,
        "demandeur_nom": member.nom,
        "demandeur_numero": member.numero_membre,
        "montant": str(loan_request.montant_demande),
        "request_id": loan_request.id,
        "admin_url": admin_url,
    }

    def _emit() -> None:
        try:
            from apps_coop.notifications.events import emit_event

            emit_event(
                "loan.credit_dossier_ready",
                member=member,  # contexte/prénom ; l'envoi part sur to_email (ops)
                to_email=ops,
                context=ctx,
            )
        except Exception:  # pragma: no cover — notif best-effort
            logger.exception("notif staff dossier prêt a échoué")

    transaction.on_commit(_emit)


@receiver(post_save, sender=LoanRequest, dispatch_uid="release_guarantee_on_request_rejected")
def _release_on_request_rejected(sender, instance: LoanRequest, **kwargs) -> None:
    from .avaliste_services import _released_request_statuses

    if instance.statut in _released_request_statuses():
        freed = release_guarantee_tranches(instance)
        # freed > 0 ⇒ vraie transition (idempotent : 0 sur les re-save) → on
        # prévient le garant une seule fois que sa caution est libérée.
        if freed > 0:
            _notify_avaliste_gel_released(instance)


@receiver(post_save, sender=Loan, dispatch_uid="release_guarantee_on_loan_closed")
def _release_on_loan_closed(sender, instance: Loan, **kwargs) -> None:
    if instance.statut != Loan.Statut.CLOTURE:
        return
    # Tranches de FUNDING (ENGAGEE) → rendues au pool quelle que soit la voie de
    # clôture (remboursement, saisie épargne, contentieux). Le hook de
    # remboursement les libère déjà au passage `just_closed` ; le faire aussi ici
    # (idempotent) « auto-répare » les clôtures non-remboursement qui, sinon,
    # laissaient les tranches ENGAGEE en l'air. Symétrique du gel garantie.
    release_loan_tranches(instance)
    if instance.loan_request_id is None:
        return
    freed = release_guarantee_tranches(instance.loan_request)
    if freed > 0:
        _notify_avaliste_gel_released(instance.loan_request)


def _notify_avaliste_gel_released(loan_request) -> None:
    """Prévient le GARANT (avaliste) que sa caution vient d'être libérée (rejet
    de la demande ou clôture du crédit). Best-effort, envoyé après commit pour
    ne pas mailer si la transaction est annulée. No-op sans consentement accepté.
    """
    from django.db import transaction

    from .models import AvalisteConsent

    consent = (
        AvalisteConsent.objects.filter(
            loan_request=loan_request,
            statut=AvalisteConsent.Statut.ACCEPTED,
        )
        .select_related("avaliste", "loan_request", "loan_request__member")
        .first()
    )
    if consent is None:
        return

    avaliste = consent.avaliste
    borrower = consent.loan_request.member
    montant = str(consent.montant_caution)

    def _emit() -> None:
        try:
            from django.conf import settings

            from apps_coop.notifications.events import emit_event

            emit_event(
                "loan.avaliste_gel_released",
                member=avaliste,
                context={
                    "prenom": avaliste.prenom,
                    "borrower_nom": borrower.nom,
                    "borrower_numero": borrower.numero_membre,
                    "montant": montant,
                    # {portal_url} du CTA — sans lui, _render retombe sur le brut.
                    "portal_url": getattr(settings, "FRONTEND_PUBLIC_URL", ""),
                },
            )
        except Exception:  # pragma: no cover — notif best-effort
            logger.exception("notif libération caution avaliste a échoué")

    transaction.on_commit(_emit)
