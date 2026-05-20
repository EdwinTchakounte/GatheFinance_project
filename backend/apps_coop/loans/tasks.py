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


logger = logging.getLogger(__name__)


_TWO_DP = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


#: Seuil en jours à partir duquel un Loan en retard bascule en contentieux.
CONTENTIEUX_THRESHOLD_DAYS = 90

#: Taux Article 12 — pénalité = 50 % des intérêts dus sur la somme manquante.
LATE_PENALTY_RATE = Decimal("0.50")


def _compute_penalty(montant_interets: Decimal, montant_total: Decimal, montant_paye: Decimal) -> Decimal:
    """Pénalité Article 12 = 50 % × intérêts proratisés sur la somme manquante.

    Si tout reste dû, c'est 50 % des intérêts de l'échéance.
    Si une partie a été payée, on calcule la pénalité au prorata.
    """
    if montant_total <= 0:
        return Decimal("0")
    reste_du = max(montant_total - montant_paye, Decimal("0"))
    ratio_du = reste_du / montant_total  # entre 0 et 1
    interets_dus = montant_interets * ratio_du
    return _q(interets_dus * LATE_PENALTY_RATE)


def suivi_retards_quotidien() -> dict:
    """Détecte les retards d'échéances et applique les conséquences Articles 12-13.

    Returns un summary structuré + record_audit.
    """
    from apps_coop.loans.models import Loan, LoanInstallment

    today = timezone.localdate()
    now = timezone.now()

    installments_examinees = 0
    passees_en_retard = 0
    penalites_appliquees = 0
    total_penalites = Decimal("0")
    loans_en_retard = 0
    loans_contentieux = 0
    erreurs = 0

    # 1) Marquer les installments dont la date_echeance est dépassée.
    overdue_qs = LoanInstallment.objects.filter(
        date_echeance__lt=today,
        statut__in=[LoanInstallment.Statut.A_VENIR, LoanInstallment.Statut.PARTIELLE],
    ).select_related("loan")

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

                # Pénalité Article 12 — appliquée 1× seulement.
                if locked.penalite_appliquee_at is None:
                    penalite = _compute_penalty(
                        Decimal(locked.montant_interets),
                        Decimal(locked.montant_total),
                        Decimal(locked.montant_paye),
                    )
                    if penalite > 0:
                        locked.montant_penalite = penalite
                        total_penalites += penalite
                        penalites_appliquees += 1
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
        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception("suivi_retards — échec installment_id=%s", inst.pk)

    # 2) Marquer les Loans concernés en `en_retard` ou `contentieux`.
    affected_loan_ids = set(
        LoanInstallment.objects
        .filter(statut=LoanInstallment.Statut.EN_RETARD)
        .values_list("loan_id", flat=True)
    )

    contentieux_cutoff = today - timedelta(days=CONTENTIEUX_THRESHOLD_DAYS)

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

                if loan.statut != new_statut:
                    old_statut = loan.statut
                    loan.statut = new_statut
                    loan.save(update_fields=["statut", "updated_at"])

                    if new_statut == Loan.Statut.EN_RETARD:
                        loans_en_retard += 1
                    else:
                        loans_contentieux += 1

                    record_audit(
                        action=f"loan.{new_statut}",
                        entite_type="Loan",
                        entite_id=loan.pk,
                        details={
                            "numero_dossier": loan.numero_dossier,
                            "previous_statut": old_statut,
                            "oldest_overdue_date": oldest_overdue.date_echeance.isoformat(),
                            "days_late": (today - oldest_overdue.date_echeance).days,
                        },
                    )
        except Exception:  # noqa: BLE001
            erreurs += 1
            logger.exception("suivi_retards — échec loan_id=%s", loan_id)

    summary = {
        "date": today.isoformat(),
        "installments_examinees": installments_examinees,
        "passees_en_retard": passees_en_retard,
        "penalites_appliquees": penalites_appliquees,
        "total_penalites": str(total_penalites),
        "loans_en_retard": loans_en_retard,
        "loans_contentieux": loans_contentieux,
        "erreurs": erreurs,
    }
    record_audit(
        action="cron.loans_overdue.run",
        entite_type="cron",
        details=summary,
    )
    logger.info("suivi_retards_quotidien summary=%s", summary)
    return summary
