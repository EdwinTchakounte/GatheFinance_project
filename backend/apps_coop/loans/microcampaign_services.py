"""Voie 3 — MICROCAMPAIGN (refonte 2026 §8 / LOT 11).

Fonctions publiques :
  * ``get_active_campaigns(profil_cible=None)`` — campagnes actuellement
    ouvertes (``actif=True`` et fenêtre courante). Filtre optionnel par
    ``profil_cible`` (égalité stricte, casse-insensible).
  * ``is_campaign_open(campaign, today=None)`` — booléen test d'ouverture.
  * ``validate_amount_against_campaign(campaign, montant)`` — checks plafond
    /plancher + quota bénéficiaires. Lève ``ValueError`` en cas d'écart.
  * ``close_campaign(campaign, reason=...)`` — idempotent ; pose
    ``actif=False`` + ``closed_at`` et émet l'event ``microcampaign.closed``.
  * ``close_expired_campaigns()`` — cron daily ; clôture toutes les campagnes
    dont ``date_fin < today`` et ``actif=True``. Renvoie un compteur.

LOT 11 livre la **fondation** : modèle + clôture. La création du Member
TEMPORAIRE + LoanRequest + Loan se branchera dans LOT 12 (eligibility
routing) une fois le routeur des 3 voies en place.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    record as record_audit,
)

from .models import MicrocreditCampaign


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lecture — campagnes actives
# ---------------------------------------------------------------------------


def get_active_campaigns(
    profil_cible: Optional[str] = None,
    *,
    today=None,
) -> QuerySet[MicrocreditCampaign]:
    """Renvoie le QuerySet des campagnes en cours (actives + dans la fenêtre).

    ``profil_cible`` optionnel filtre par profil ciblé (égalité casse-insensible).
    """
    today = today or timezone.localdate()
    qs = MicrocreditCampaign.objects.filter(
        actif=True,
        date_debut__lte=today,
        date_fin__gte=today,
    )
    if profil_cible:
        qs = qs.filter(profil_cible__iexact=profil_cible.strip())
    return qs.order_by("date_fin", "id")


def is_campaign_open(campaign: MicrocreditCampaign, *, today=None) -> bool:
    """True si la campagne accepte de nouvelles demandes aujourd'hui."""
    today = today or timezone.localdate()
    return (
        bool(campaign.actif)
        and campaign.date_debut <= today <= campaign.date_fin
    )


# ---------------------------------------------------------------------------
# Validation amount + quota
# ---------------------------------------------------------------------------


def _beneficiaires_count(campaign: MicrocreditCampaign) -> int:
    """Nombre de bénéficiaires déjà rattachés (Members TEMPORAIRE)."""
    return campaign.beneficiaires.count()


def validate_amount_against_campaign(
    campaign: MicrocreditCampaign,
    montant,
) -> None:
    """Lève ``ValueError`` si le montant viole les bornes ou le quota.

    Vérifications dans l'ordre :
      1. Campagne ouverte.
      2. Montant ∈ [montant_min, montant_max].
      3. Quota bénéficiaires non atteint si ``plafond_beneficiaires`` posé.
    """
    if not is_campaign_open(campaign):
        raise ValueError(
            f"Campagne #{campaign.id} fermée — date_fin={campaign.date_fin}, "
            f"actif={campaign.actif}."
        )

    montant_d = Decimal(montant)
    if montant_d <= 0:
        raise ValueError("Montant demandé doit être strictement positif.")
    if montant_d < Decimal(campaign.montant_min):
        raise ValueError(
            f"Montant {montant_d} < plancher campagne {campaign.montant_min}."
        )
    if montant_d > Decimal(campaign.montant_max):
        raise ValueError(
            f"Montant {montant_d} > plafond campagne {campaign.montant_max}."
        )

    if campaign.plafond_beneficiaires is not None:
        used = _beneficiaires_count(campaign)
        if used >= campaign.plafond_beneficiaires:
            raise ValueError(
                f"Quota bénéficiaires atteint pour campagne #{campaign.id} "
                f"({used}/{campaign.plafond_beneficiaires})."
            )


# ---------------------------------------------------------------------------
# Clôture
# ---------------------------------------------------------------------------


@transaction.atomic
def close_campaign(
    campaign: MicrocreditCampaign,
    *,
    reason: str = "manual",
) -> MicrocreditCampaign:
    """Pose ``actif=False`` + ``closed_at`` + audit. Idempotent."""
    campaign = (
        MicrocreditCampaign.objects.select_for_update().get(pk=campaign.pk)
    )
    if not campaign.actif:
        return campaign

    now = timezone.now()
    campaign.actif = False
    campaign.closed_at = now
    campaign.close_reason = (reason or "manual").strip()[:64]
    campaign.save(update_fields=["actif", "closed_at", "close_reason", "updated_at"])

    record_audit(
        action="microcampaign.closed",
        entite_type="MicrocreditCampaign",
        entite_id=campaign.id,
        details={"reason": campaign.close_reason, "closed_at": now.isoformat()},
    )
    _emit("microcampaign.closed", campaign)
    return campaign


def close_expired_campaigns(*, today=None) -> dict:
    """Cron — clôture toutes les campagnes ``actif=True`` dont la date_fin est passée.

    Renvoie ``{"closed": N, "checked": M}`` pour les logs cron. Idempotent
    (sécurisé pour rejouer le cron plusieurs fois dans la journée).
    """
    today = today or timezone.localdate()
    checked = MicrocreditCampaign.objects.filter(
        actif=True, date_fin__lt=today
    )
    closed = 0
    for campaign in checked:
        try:
            close_campaign(campaign, reason="expired")
            closed += 1
        except Exception:  # noqa: BLE001 — un échec ne doit pas casser le cron
            logger.exception(
                "close_expired_campaigns — échec campaign_id=%s", campaign.pk
            )
    return {"checked": checked.count() if closed == 0 else closed, "closed": closed}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _emit(event_code: str, campaign: MicrocreditCampaign) -> None:
    """Émission best-effort (LOT 11 — pas de template requis)."""
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            event_code,
            member=None,
            context={
                "campagne": campaign.nom,
                "date_fin": str(campaign.date_fin),
                "close_reason": campaign.close_reason or "",
            },
        )
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning(
            "emit_event(%s) a échoué pour campaign #%s", event_code, campaign.id
        )


# get_int_setting is imported in case downstream LOT 12 needs default tunables
# from this module — kept here to keep the import surface stable.
_ = get_int_setting  # noqa: F841 (placeholder, no warn)


# ---------------------------------------------------------------------------
# Candidature visiteur (non-membre) + onboarding à l'acceptation (2026)
# ---------------------------------------------------------------------------


@transaction.atomic
def create_public_application(
    campaign, *, nom, prenom, phone, email, montant, motif="", documents=None
):
    """Enregistre une candidature d'un VISITEUR non-membre.

    Le compte N'EST PAS créé ici (anti-abus) : seule l'acceptation admin
    matérialise le compte. Lève ``ValueError`` si la campagne n'accepte pas
    les visiteurs (``membre_requis``), si elle est fermée, si le montant est
    hors bornes, ou s'il manque une pièce exigée (``documents_requis``).

    ``documents`` = liste de tuples ``(label, uploaded_file)`` fournis par le
    candidat. Chaque libellé de ``campaign.documents_requis`` doit avoir un
    fichier correspondant.
    """
    from .models import CampaignApplication, CampaignApplicationDocument

    if campaign.membre_requis:
        raise ValueError(
            "Cette campagne est réservée aux membres — connecte-toi et postule "
            "depuis ton espace crédit."
        )
    if not is_campaign_open(campaign):
        raise ValueError("Cette campagne n'est plus ouverte aux candidatures.")
    # Quantifie à 2 décimales (money_field) pour éviter tout débordement de
    # précision à l'INSERT (source possible d'un 500 non-ValueError).
    from decimal import ROUND_HALF_UP, InvalidOperation

    from apps_coop.common import MONEY_DECIMAL_PLACES

    try:
        montant = Decimal(montant).quantize(
            Decimal(1).scaleb(-MONEY_DECIMAL_PLACES), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Montant invalide.")
    validate_amount_against_campaign(campaign, montant)
    if not (email or "").strip():
        raise ValueError("Un email est requis pour créer ton accès.")

    # Contrôle des pièces exigées : chaque libellé doit avoir un fichier.
    requis = [str(d).strip() for d in (campaign.documents_requis or []) if str(d).strip()]
    fournis = {str(lbl).strip(): f for lbl, f in (documents or []) if f is not None}
    manquants = [lbl for lbl in requis if not fournis.get(lbl)]
    if manquants:
        raise ValueError(
            "Pièces justificatives manquantes : " + ", ".join(manquants) + "."
        )

    app = CampaignApplication.objects.create(
        campaign=campaign,
        nom=nom.strip(),
        prenom=prenom.strip(),
        phone=(phone or "").strip(),
        email=email.strip().lower(),
        montant_demande=Decimal(montant),
        motif=(motif or "").strip(),
    )
    for lbl in requis:
        CampaignApplicationDocument.objects.create(
            application=app, label=lbl, fichier=fournis[lbl]
        )
    return app


@transaction.atomic
def accept_campaign_application(application, *, decided_by):
    """Accepte une candidature → crée le compte bénéficiaire (statut ACTIF,
    accès complet, SANS les frais d'adhésion 13K), envoie le mail de
    définition de mot de passe, et ouvre un ``LoanRequest`` en instruction.

    Idempotent : une candidature déjà acceptée est renvoyée telle quelle.
    """
    from datetime import date

    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from apps_coop.members.models import Member
    from apps_coop.members.services import (
        _random_password,
        _send_welcome_email,
        generate_numero_membre,
    )
    from apps_coop.savings.models import SavingsAccount

    from .models import CampaignApplication, LoanRequest
    from .terms import duration_months_for

    if application.statut == CampaignApplication.Statut.ACCEPTEE and application.member_id:
        return application
    if application.statut != CampaignApplication.Statut.EN_ATTENTE:
        raise ValueError(f"Candidature déjà décidée (statut={application.statut}).")

    campaign = application.campaign
    montant = Decimal(application.montant_demande)
    # Re-contrôle au moment de l'acceptation (campagne encore ouverte + bornes).
    validate_amount_against_campaign(campaign, montant)

    User = get_user_model()
    email = application.email.strip().lower()
    user, user_created = User.objects.get_or_create(
        email=email,
        defaults={
            "username": email,
            "first_name": application.prenom,
            "last_name": application.nom,
            "is_active": True,
        },
    )
    if user_created:
        user.set_password(_random_password())
        user.save(update_fields=["password"])
    group, _ = Group.objects.get_or_create(name="member")
    user.groups.add(group)

    member, _created = Member.objects.get_or_create(
        user=user,
        defaults={
            "numero_membre": generate_numero_membre(),
            "nom": application.nom,
            "prenom": application.prenom,
            "phone": application.phone,
            # Accès complet immédiat SANS les 13K. Le FK microcampaign marque
            # l'origine « bénéficiaire campagne » (Q15 assoupli 2026).
            "statut": Member.Statut.ACTIF,
            "date_adhesion": date.today(),
            "microcampaign": campaign,
        },
    )
    SavingsAccount.objects.get_or_create(
        member=member,
        defaults={"solde": 0, "date_ouverture": date.today(), "taux_interet_applique": 0},
    )

    # L'acceptation de la candidature FAIT office de validation campagne
    # (pas de 2e porte). Restent les frais à régler à la demande de crédit :
    #   • frais d'étude (propres à la campagne ou standard)
    #   • frais de CARNET — obligatoire pour un membre créé via campagne
    #     (les versements collecte s'imputent au carnet). Facturé + payé ici.
    # La demande reste EN_ATTENTE tant que ces frais ne sont pas soldés.
    from .services import campaign_member_needs_carnet, study_fee_for

    _study_fee = study_fee_for(campaign)
    _needs_carnet = campaign_member_needs_carnet(member)
    _en_attente = _study_fee > 0 or _needs_carnet
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=duration_months_for(montant),
        motif=application.motif or f"Candidature campagne {campaign.nom}",
        microcampaign=campaign,
        statut=(
            LoanRequest.Statut.EN_ATTENTE
            if _en_attente
            else LoanRequest.Statut.EN_INSTRUCTION
        ),
        # Rien à payer côté étude → marqué payé (le carnet reste, lui, dû et
        # ouvrira l'instruction à son règlement via _hook_carnet_fees).
        frais_demande_credit_paye=(_study_fee <= 0),
    )

    application.statut = CampaignApplication.Statut.ACCEPTEE
    application.member = member
    application.loan_request = lr
    application.decide_par = decided_by
    application.date_decision = timezone.now()
    application.save(update_fields=[
        "statut", "member", "loan_request", "decide_par", "date_decision", "updated_at",
    ])

    record_audit(
        action="microcampaign.application_accepted",
        entite_type="CampaignApplication",
        entite_id=application.id,
        user=decided_by,
        details={
            "campaign_id": campaign.id,
            "member_id": member.id,
            "numero_membre": member.numero_membre,
            "loan_request_id": lr.id,
        },
    )
    # Mail de définition de mot de passe (compte créé) — émis au commit.
    transaction.on_commit(lambda: _send_welcome_email(member, email))
    return application


def reject_campaign_application(application, *, decided_by, motif_rejet):
    """Rejette une candidature visiteur. Aucun compte n'est créé."""
    from .models import CampaignApplication

    if application.statut != CampaignApplication.Statut.EN_ATTENTE:
        raise ValueError(f"Candidature déjà décidée (statut={application.statut}).")
    motif = (motif_rejet or "").strip()
    if not motif:
        raise ValueError("Motif de rejet requis.")
    application.statut = CampaignApplication.Statut.REJETEE
    application.motif_rejet = motif
    application.decide_par = decided_by
    application.date_decision = timezone.now()
    application.save(update_fields=[
        "statut", "motif_rejet", "decide_par", "date_decision", "updated_at",
    ])
    record_audit(
        action="microcampaign.application_rejected",
        entite_type="CampaignApplication",
        entite_id=application.id,
        user=decided_by,
        details={"campaign_id": application.campaign_id, "motif": motif},
    )
    return application
