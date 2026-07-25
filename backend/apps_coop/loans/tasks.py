"""Scheduled tasks for the loans domain.

Wired by ``apps_coop.audit.management.commands.seed_q_schedules`` to run via
django-q2's qcluster worker.

Le cron ``loans.overdue.daily`` tourne tous les jours à 03h00.

Articles 12-13 du Règlement Intérieur appliqués :
  - Article 12 : pénalité de **50 %** sur les intérêts dus de la somme
    manquante, appliquée 1× par installment quand il bascule en retard.
  - Article 13 : conséquences du non-remboursement — le Loan passe en
    ``en_retard`` dès qu'une installment est en retard, puis en
    ``contentieux`` si le retard dépasse 90 jours sur au moins une échéance.
    La mise en demeure / poursuites judiciaires est ensuite **manuelle**
    (l'admin déclenche depuis Django admin une fois le Loan en contentieux).

Idempotence : le cron est tournable plusieurs fois par jour sans dégât. La
pénalité n'est pas réappliquée (champ ``penalite_appliquee_at``), et les
statuts ne sont changés que s'ils diffèrent.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.portal_urls import portal_url


logger = logging.getLogger(__name__)


_TWO_DP = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


#: Défaut réglementaire (Article 13) — modifiable côté admin via l'AppSetting
#: ``loans.contentieux.threshold_days``. La valeur effective est lue par
#: ``get_int_setting`` au moment du cron pour qu'un ajustement admin
#: s'applique sans redéploiement (EXT-1).
CONTENTIEUX_THRESHOLD_DAYS = 90

#: Défaut réglementaire Article 12 — pénalité = 50 % des intérêts dus sur la
#: somme manquante. Modifiable côté admin via ``RateParam.LATE_PENALTY`` (BR2).
LATE_PENALTY_RATE = Decimal("0.50")


def _compute_penalty(
    montant_interets: Decimal,
    montant_total: Decimal,
    montant_paye: Decimal,
    taux: Decimal | None = None,
) -> Decimal:
    """Pénalité Article 12 = ``taux`` × intérêts proratisés sur la somme manquante.

    ``taux`` par défaut = ``RateParam.LATE_PENALTY`` (50 % réglementaire,
    modifiable côté admin). Si tout reste dû, c'est ``taux`` × intérêts de
    l'échéance ; si une partie a été payée, on calcule au prorata.
    """
    if montant_total <= 0:
        return Decimal("0")
    if taux is None:
        from apps_coop.payments.models import RateParam
        from apps_coop.payments.rates import get_rate

        taux = get_rate(RateParam.Code.LATE_PENALTY)
    reste_du = max(montant_total - montant_paye, Decimal("0"))
    ratio_du = reste_du / montant_total  # entre 0 et 1
    interets_dus = montant_interets * ratio_du
    return _q(interets_dus * taux)


def suivi_retards_quotidien() -> dict:
    """Détecte les retards d'échéances et applique les conséquences Articles 12-13.

    Returns un summary structuré + record_audit.
    """
    from apps_coop.loans.models import Loan, LoanInstallment
    from apps_coop.payments.models import RateParam
    from apps_coop.payments.rates import get_rate

    today = timezone.localdate()
    now = timezone.now()
    # EXT-versioning : on N'utilise PLUS un taux global lu une fois — chaque
    # crédit a son ``taux_penalite`` figé au décaissement. ``fallback_taux``
    # ne sert que pour les crédits legacy (taux_penalite = NULL) → garantit
    # la rétrocompat sans changer le résultat numérique.
    fallback_taux = get_rate(RateParam.Code.LATE_PENALTY)

    # Nouvelle règle 2026 (REMPLACE Art.12) : la pénalité financière est
    # désormais GLOBALE, appliquée au franchissement de la date limite globale.
    # La phase « pénalité par échéance » est désactivée par défaut. L'admin
    # peut la réactiver via ``loans.penalite_par_echeance.enabled = true``
    # pour revenir au modèle Art.12 (cumul avec la pénalité globale).
    from apps_coop.audit.services import get_str_setting

    penalite_par_echeance_enabled = (
        get_str_setting("loans.penalite_par_echeance.enabled", "false").lower()
        in {"true", "1", "yes"}
    )

    installments_examinees = 0
    passees_en_retard = 0
    penalites_appliquees = 0
    total_penalites = Decimal("0")
    loans_en_retard = 0
    loans_contentieux = 0
    erreurs = 0
    # Pénalités posées CE passage, par crédit — ajoutées au solde_restant
    # en phase 2 pour les rendre exigibles (sinon calculées mais jamais dues).
    penalites_par_loan: dict[int, Decimal] = {}
    # Échéances passées en retard CE passage → notifications membre (phase 3).
    # Tuples (loan_id, numero_echeance, montant_total, penalite).
    notifs_retard: list[tuple[int, int, Decimal, Decimal]] = []

    # 1) Marquer les installments dont la date_echeance est dépassée.
    # Filet de sécurité : on EXCLUT les crédits pas encore décaissés — on ne
    # marque pas en retard (ni ne pénalise) une échéance dont l'argent n'a
    # jamais été versé au membre.
    overdue_qs = LoanInstallment.objects.filter(
        date_echeance__lt=today,
        statut__in=[LoanInstallment.Statut.A_VENIR, LoanInstallment.Statut.PARTIELLE],
    ).exclude(loan__en_attente_decaissement=True).select_related("loan")

    for inst in overdue_qs:
        installments_examinees += 1
        try:
            with transaction.atomic():
                locked = (
                    LoanInstallment.objects
                    .select_for_update()
                    .select_related("loan")
                    .get(pk=inst.pk)
                )
                # Re-check sous verrou — un remboursement concurrent pourrait
                # avoir clôturé l'échéance entre temps.
                if locked.statut not in (
                    LoanInstallment.Statut.A_VENIR,
                    LoanInstallment.Statut.PARTIELLE,
                ):
                    continue

                # Pénalité Article 12 — DÉSACTIVÉE par défaut depuis 2026
                # (remplacée par la pénalité GLOBALE au franchissement de la
                # date limite). Réactivable via AppSetting
                # ``loans.penalite_par_echeance.enabled = true``.
                if penalite_par_echeance_enabled and locked.penalite_appliquee_at is None:
                    # Taux figé sur le crédit (EXT-versioning) ; legacy → fallback.
                    taux_loan = (
                        Decimal(locked.loan.taux_penalite)
                        if locked.loan.taux_penalite is not None
                        else fallback_taux
                    )
                    penalite = _compute_penalty(
                        Decimal(locked.montant_interets),
                        Decimal(locked.montant_total),
                        Decimal(locked.montant_paye),
                        taux=taux_loan,
                    )
                    if penalite > 0:
                        locked.montant_penalite = penalite
                        total_penalites += penalite
                        penalites_appliquees += 1
                        penalites_par_loan[locked.loan_id] = (
                            penalites_par_loan.get(locked.loan_id, Decimal("0")) + penalite
                        )
                    locked.penalite_appliquee_at = now

                locked.statut = LoanInstallment.Statut.EN_RETARD
                locked.save(update_fields=[
                    "statut",
                    "montant_penalite",
                    "penalite_appliquee_at",
                    "updated_at",
                ])
                passees_en_retard += 1

                record_audit(
                    action="loan_installment.overdue",
                    entite_type="LoanInstallment",
                    entite_id=locked.pk,
                    details={
                        "loan_id": locked.loan_id,
                        "numero_echeance": locked.numero_echeance,
                        "date_echeance": locked.date_echeance.isoformat(),
                        "days_late": (today - locked.date_echeance).days,
                        "montant_penalite": str(locked.montant_penalite),
                    },
                )
                notifs_retard.append((
                    locked.loan_id,
                    locked.numero_echeance,
                    Decimal(locked.montant_total),
                    Decimal(locked.montant_penalite),
                ))
        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception("suivi_retards — échec installment_id=%s", inst.pk)

    # 2) Marquer les Loans concernés en `en_retard` ou `contentieux`.
    affected_loan_ids = set(
        LoanInstallment.objects
        .filter(statut=LoanInstallment.Statut.EN_RETARD)
        .values_list("loan_id", flat=True)
    )
    # Toujours inclure les crédits qui ont reçu une pénalité ce passage.
    affected_loan_ids |= set(penalites_par_loan)

    from apps_coop.audit.services import get_int_setting

    threshold_days = get_int_setting(
        "loans.contentieux.threshold_days", CONTENTIEUX_THRESHOLD_DAYS
    )
    contentieux_cutoff = today - timedelta(days=threshold_days)

    for loan_id in affected_loan_ids:
        try:
            with transaction.atomic():
                loan = (
                    Loan.objects
                    .select_for_update()
                    .get(pk=loan_id)
                )
                if loan.statut == Loan.Statut.CLOTURE:
                    continue  # un Loan clôturé n'a pas à changer

                # Échéance la plus ancienne en retard
                oldest_overdue = (
                    LoanInstallment.objects
                    .filter(loan=loan, statut=LoanInstallment.Statut.EN_RETARD)
                    .order_by("date_echeance")
                    .first()
                )
                if oldest_overdue is None:
                    continue

                if oldest_overdue.date_echeance <= contentieux_cutoff:
                    new_statut = Loan.Statut.CONTENTIEUX
                else:
                    new_statut = Loan.Statut.EN_RETARD

                # Rendre la pénalité exigible : on l'ajoute au solde restant.
                extra_penalite = penalites_par_loan.get(loan_id, Decimal("0"))
                update_fields: list[str] = []
                if extra_penalite > 0:
                    loan.solde_restant = _q(Decimal(loan.solde_restant) + extra_penalite)
                    update_fields.append("solde_restant")

                old_statut = loan.statut
                if loan.statut != new_statut:
                    loan.statut = new_statut
                    update_fields.append("statut")
                    if new_statut == Loan.Statut.EN_RETARD:
                        loans_en_retard += 1
                    else:
                        loans_contentieux += 1

                if update_fields:
                    update_fields.append("updated_at")
                    loan.save(update_fields=update_fields)

                if loan.statut != old_statut or extra_penalite > 0:
                    record_audit(
                        action=f"loan.{loan.statut}",
                        entite_type="Loan",
                        entite_id=loan.pk,
                        details={
                            "numero_dossier": loan.numero_dossier,
                            "previous_statut": old_statut,
                            "oldest_overdue_date": oldest_overdue.date_echeance.isoformat(),
                            "days_late": (today - oldest_overdue.date_echeance).days,
                            "penalite_ajoutee": str(extra_penalite),
                            "solde_restant": str(loan.solde_restant),
                        },
                    )
        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception("suivi_retards — échec loan_id=%s", loan_id)

    # 3) Notifier chaque membre dont une échéance vient de passer en retard
    #    (Articles 12-13). Hors transaction : un échec d'email ne doit pas
    #    annuler l'application de la pénalité déjà committée.
    retards_notifies = 0
    if notifs_retard:
        from django.conf import settings as dj_settings

        from apps_coop.loans.models import Loan
        from apps_coop.notifications.events import emit_event

        portal = portal_url()
        for loan_id, num_ech, montant_total, penalite in notifs_retard:
            try:
                loan = Loan.objects.select_related("member__user").get(pk=loan_id)
                member = loan.member
                if not getattr(member.user, "email", None):
                    continue
                emit_event(
                    "loan.installment_overdue",
                    member=member,
                    context={
                        "prenom": member.prenom,
                        "numero_dossier": loan.numero_dossier,
                        "numero_echeance": num_ech,
                        "montant_du": f"{int(montant_total):,}".replace(",", " "),
                        "penalite": f"{int(penalite):,}".replace(",", " "),
                        "portal_url": portal,
                    },
                )
                retards_notifies += 1
            except Exception:  # noqa: BLE001
                logger.warning(
                    "loan.installment_overdue email skipped loan_id=%s", loan_id,
                    exc_info=True,
                )

    # 4) Phase B — Pénalité GLOBALE (nouvelle règle, depuis 2026-05).
    #    Pour tout Loan dont la date limite globale est franchie ET dont le
    #    solde restant > 0 ET sans pénalité globale déjà appliquée → appliquer
    #    ``taux × solde_restant``. Notification au membre via emit_event.
    penalites_globales_appliquees, penalites_globales_notifs = _phase_penalite_globale(
        today
    )

    # 5) Phase C — Saisie épargne (R1) au passage en contentieux.
    #    ``loans.penalite_globale.grace_days`` jours après l'application de la
    #    pénalité globale, si le solde n'est toujours pas soldé, on bascule en
    #    CONTENTIEUX et on prélève l'épargne du membre. Notification + audit.
    contentieux_basculs, contentieux_saisies, contentieux_poursuites = (
        _phase_contentieux_et_saisie(today)
    )

    summary = {
        "date": today.isoformat(),
        "installments_examinees": installments_examinees,
        "passees_en_retard": passees_en_retard,
        "penalites_appliquees": penalites_appliquees,
        "total_penalites": str(total_penalites),
        "loans_en_retard": loans_en_retard,
        "loans_contentieux": loans_contentieux,
        "retards_notifies": retards_notifies,
        "penalites_globales_appliquees": penalites_globales_appliquees,
        "penalites_globales_notifs": penalites_globales_notifs,
        "contentieux_basculs": contentieux_basculs,
        "contentieux_saisies": contentieux_saisies,
        "contentieux_poursuites": contentieux_poursuites,
        "erreurs": erreurs,
    }
    record_audit(
        action="cron.loans_overdue.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("suivi_retards_quotidien summary=%s", summary)
    return summary


#: Défaut du rappel proactif J-N — modifiable côté admin via l'AppSetting
#: ``loans.due_soon.lead_days``. ``DUE_SOON_LEAD_DAYS`` reste la valeur de
#: repli sûre si la ligne DB est absente (EXT-1).
DUE_SOON_LEAD_DAYS = 3


def rappel_echeances_proches() -> dict:
    """Rappel proactif : prévient le membre ``DUE_SOON_LEAD_DAYS`` jours avant
    une échéance à venir, pour réduire les retards (et donc les pénalités).

    Idempotence naturelle : ne cible que les échéances tombant exactement à
    ``today + DUE_SOON_LEAD_DAYS``. Comme le cron tourne 1×/jour, chaque
    échéance ne déclenche qu'un seul rappel (pas de champ d'état nécessaire).
    """
    from django.conf import settings as dj_settings

    from apps_coop.loans.models import LoanInstallment
    from apps_coop.notifications.events import emit_event

    from apps_coop.audit.services import get_int_setting

    today = timezone.localdate()
    lead_days = get_int_setting("loans.due_soon.lead_days", DUE_SOON_LEAD_DAYS)
    target = today + timedelta(days=lead_days)
    portal = portal_url()

    qs = (
        LoanInstallment.objects
        .filter(
            date_echeance=target,
            statut__in=[
                LoanInstallment.Statut.A_VENIR,
                LoanInstallment.Statut.PARTIELLE,
            ],
        )
        .select_related("loan", "loan__member__user")
    )

    examinees = 0
    rappels_envoyes = 0
    erreurs = 0
    for inst in qs:
        examinees += 1
        try:
            member = inst.loan.member
            if not getattr(member.user, "email", None):
                continue
            emit_event(
                "loan.installment_due_soon",
                member=member,
                context={
                    "prenom": member.prenom,
                    "numero_dossier": inst.loan.numero_dossier,
                    "montant_echeance": f"{int(inst.montant_total):,}".replace(",", " "),
                    "date_echeance": inst.date_echeance.isoformat(),
                    "portal_url": portal,
                },
            )
            rappels_envoyes += 1
        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.warning(
                "rappel_echeances — échec installment_id=%s", inst.pk, exc_info=True
            )

    summary = {
        "date": today.isoformat(),
        "target_date": target.isoformat(),
        "echeances_examinees": examinees,
        "rappels_envoyes": rappels_envoyes,
        "erreurs": erreurs,
    }
    record_audit(
        action="cron.loans_due_soon.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("rappel_echeances_proches summary=%s", summary)
    return summary


# ---------------------------------------------------------------------------
# Cycle contentieux (phase B + C) — appelés depuis ``suivi_retards_quotidien``
# ---------------------------------------------------------------------------


#: Délai en jours entre l'application de la pénalité globale et le passage en
#: CONTENTIEUX (déclenche la saisie épargne). Modifiable via AppSetting
#: ``loans.penalite_globale.grace_days``.
DEFAULT_PENALITE_GLOBALE_GRACE_DAYS = 30


def _phase_penalite_globale(today) -> tuple[int, int]:
    """Phase B — applique la pénalité globale aux crédits dont la date limite
    globale est franchie sans remboursement complet.

    Retourne ``(appliquees, notifications_envoyees)``.
    """
    from apps_coop.loans.models import Loan
    from apps_coop.loans.services import apply_global_penalty
    from apps_coop.notifications.events import emit_event

    # On annote chaque Loan candidat avec la date max de ses échéances pour
    # filtrer ceux dont la date limite globale est dépassée.
    from django.db.models import Max

    candidats = (
        Loan.objects.filter(
            statut__in=[Loan.Statut.ACTIF, Loan.Statut.EN_RETARD],
            solde_restant__gt=0,
            # Filet de sécurité : pas de pénalité globale sur un crédit non décaissé.
            en_attente_decaissement=False,
            penalite_globale_appliquee_at__isnull=True,
        )
        .annotate(date_limite=Max("installments__date_echeance"))
        .filter(date_limite__lt=today)
        .select_related("member__user")
    )

    appliquees = 0
    notifs = 0
    for loan in candidats:
        try:
            penalite = apply_global_penalty(loan)
        except Exception:  # noqa: BLE001
            logger.exception("apply_global_penalty échoué loan_id=%s", loan.pk)
            continue
        if penalite <= 0:
            continue
        appliquees += 1

        # Notification au membre — best-effort (hors transaction).
        try:
            loan.refresh_from_db()
            if getattr(loan.member.user, "email", None):
                emit_event(
                    "loan.penalite_globale_appliquee",
                    member=loan.member,
                    context={
                        "prenom": loan.member.prenom,
                        "numero_dossier": loan.numero_dossier,
                        "penalite": f"{int(penalite):,}".replace(",", " "),
                        "nouveau_solde": f"{int(loan.solde_restant):,}".replace(",", " "),
                        "delai_grace_jours": _grace_days(),
                    },
                )
                notifs += 1
        except Exception:  # noqa: BLE001
            logger.warning(
                "loan.penalite_globale_appliquee email skipped loan_id=%s", loan.pk,
                exc_info=True,
            )
    return appliquees, notifs


def _grace_days() -> int:
    """Délai (jours) de grâce après la pénalité globale avant contentieux."""
    from apps_coop.audit.services import get_int_setting

    return get_int_setting(
        "loans.penalite_globale.grace_days", DEFAULT_PENALITE_GLOBALE_GRACE_DAYS
    )


def _phase_contentieux_et_saisie(today) -> tuple[int, int, int]:
    """Phase C — bascule en CONTENTIEUX + saisie épargne automatique (R1).

    Pour tout Loan avec ``penalite_globale_appliquee_at + grace_days <= today``
    et ``solde_restant > 0`` non encore saisi → marquer CONTENTIEUX, prélever
    l'épargne, flag poursuites si insuffisant.

    Retourne ``(basculs_contentieux, saisies, poursuites)``.
    """
    from datetime import timedelta

    from apps_coop.loans.models import Loan
    from apps_coop.loans.services import seize_member_savings_for_loan
    from apps_coop.notifications.events import emit_event

    grace = _grace_days()
    cutoff_dt = timezone.now() - timedelta(days=grace)

    candidats = Loan.objects.filter(
        penalite_globale_appliquee_at__lte=cutoff_dt,
        solde_restant__gt=0,
        epargne_saisie_at__isnull=True,
        # Filet de sécurité : pas de contentieux/saisie sur un crédit non décaissé.
        en_attente_decaissement=False,
    ).select_related("member__user")

    basculs = 0
    saisies = 0
    poursuites = 0

    for loan in candidats:
        try:
            # Marquer le passage en CONTENTIEUX (idempotent — on ne ré-écrit pas
            # contentieux_declenche_at si déjà posé).
            if loan.contentieux_declenche_at is None:
                loan.contentieux_declenche_at = timezone.now()
                loan.statut = Loan.Statut.CONTENTIEUX
                loan.save(update_fields=[
                    "contentieux_declenche_at", "statut", "updated_at"
                ])
                record_audit(
                    action="loan.contentieux_declenche",
                    entite_type="Loan",
                    entite_id=loan.pk,
                    details={
                        "numero_dossier": loan.numero_dossier,
                        "solde_restant": str(loan.solde_restant),
                    },
                )
                basculs += 1

            # Saisie épargne (R1).
            result = seize_member_savings_for_loan(loan)
            if not result.get("no_op"):
                saisies += 1
                if result.get("poursuite"):
                    poursuites += 1

            # Notifications membre — best-effort, hors transaction.
            loan.refresh_from_db()
            if getattr(loan.member.user, "email", None):
                emit_event(
                    "loan.savings_seized",
                    member=loan.member,
                    context={
                        "prenom": loan.member.prenom,
                        "numero_dossier": loan.numero_dossier,
                        "montant_saisi": f"{int(result['saisie']):,}".replace(",", " "),
                        "solde_restant_apres": f"{int(result['solde_restant_apres']):,}".replace(",", " "),
                    },
                )
                if result.get("poursuite"):
                    emit_event(
                        "loan.poursuite_engaged",
                        member=loan.member,
                        context={
                            "prenom": loan.member.prenom,
                            "numero_dossier": loan.numero_dossier,
                            "reliquat": f"{int(result['solde_restant_apres']):,}".replace(",", " "),
                        },
                    )
        except Exception:  # noqa: BLE001
            logger.exception(
                "_phase_contentieux_et_saisie — échec loan_id=%s", loan.pk
            )

    return basculs, saisies, poursuites


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 8 : cron funding 24h
# ---------------------------------------------------------------------------


def funding_window_expiry_task() -> dict:
    """Wrapper module-level pour django-q2 (cron toutes les ~15min).

    Délègue à ``funding_services.funding_window_expiry``. Pose AUTO_ACCEPTED
    sur les ``LenderConsentRequest`` PENDING dont la deadline 24h est passée,
    puis finalise les ``LoanFundingRequest`` qui n'ont plus d'attente. Retourne
    un dict compteurs pour les logs cron.
    """
    from .funding_services import funding_window_expiry

    try:
        result = funding_window_expiry()
    except Exception:  # noqa: BLE001
        logger.exception("funding_window_expiry_task — échec")
        return {"auto_accepted": 0, "settled": 0, "skipped": 0, "error": True}

    logger.info(
        "funding_window_expiry_task — auto_accepted=%s settled=%s skipped=%s",
        result.get("auto_accepted"),
        result.get("settled"),
        result.get("skipped"),
    )
    return result


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 11 : cron clôture micro-campagnes expirées
# ---------------------------------------------------------------------------


def microcampaign_close_expired_task() -> dict:
    """Wrapper module-level pour django-q2 (cron daily).

    Délègue à ``microcampaign_services.close_expired_campaigns``. Pose
    ``actif=False`` sur les ``MicrocreditCampaign`` dont la ``date_fin`` est
    passée et qui sont encore marquées actives. Renvoie un dict compteurs.
    """
    from .microcampaign_services import close_expired_campaigns

    try:
        result = close_expired_campaigns()
    except Exception:  # noqa: BLE001
        logger.exception("microcampaign_close_expired_task — échec")
        return {"closed": 0, "checked": 0, "error": True}

    logger.info(
        "microcampaign_close_expired_task — closed=%s",
        result.get("closed"),
    )
    return result


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 14 : cron escalade judiciaire auto/hybrid
# ---------------------------------------------------------------------------


def judicial_auto_escalation_task() -> dict:
    """Wrapper module-level pour django-q2 (cron daily).

    Délègue à ``judicial_services.auto_escalate_eligible_loans``. No-op si
    ``loans.judicial_escalation.mode == "manual"`` (kill-switch admin).
    """
    from .judicial_services import auto_escalate_eligible_loans

    try:
        result = auto_escalate_eligible_loans()
    except Exception:  # noqa: BLE001
        logger.exception("judicial_auto_escalation_task — échec")
        return {"opened": 0, "checked": 0, "error": True}

    logger.info(
        "judicial_auto_escalation_task — mode=%s checked=%s opened=%s",
        result.get("mode"),
        result.get("checked"),
        result.get("opened"),
    )
    return result
