"""Escalade judiciaire — phases D/E (refonte 2026 §9.3-9.4 / LOT 14).

API publique :

  * ``open_judicial_escalation(loan, *, motif, declenche_par, mode)`` —
    pose la ``JudicialEscalation`` en statut ``EN_INSTANCE``. Idempotent (1
    par crédit). Guards : ``poursuite_judiciaire_at`` non NULL + reliquat.
  * ``record_judicial_decision(escalation, *, decision_date, biens_saisissables)``
    — transition ``EN_INSTANCE → DECISION_RENDUE``.
  * ``record_judicial_execution(escalation, *, execution_date, montant_recouvre, biens_saisis)``
    — transition ``DECISION_RENDUE → EXECUTEE`` ; décrémente
    ``Loan.solde_restant`` ; clôture le crédit si solde == 0.
  * ``classer_sans_suite(escalation, *, motif)`` — abandon admin
    (``EN_INSTANCE → CLASSEE_SANS_SUITE``). Irrécouvrable, classé.
  * ``auto_escalate_eligible_loans()`` — cron daily. Ouvre une escalade pour
    chaque Loan dont ``poursuite_judiciaire_at < now - delay_days`` sans
    escalade existante, si le mode admin est ``"auto"`` ou ``"hybrid"``.

**Tunables admin** (libre arbitre total) :

  - ``loans.judicial_escalation.mode`` (``"manual"`` défaut) — modes
    ``manual``/``auto``/``hybrid``.
  - ``loans.judicial_escalation.delay_days`` (60) — jours après
    ``poursuite_judiciaire_at`` avant déclenchement auto.
  - ``loans.judicial_escalation.notify_before_days`` (7) — préavis en
    mode hybrid (LOT 14+ wiring notif).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import (
    get_int_setting,
    get_str_setting,
    record as record_audit,
)

from .models import JudicialEscalation, Loan


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------


_VALID_MODES = {"manual", "auto", "hybrid"}


def _mode() -> str:
    raw = (get_str_setting("loans.judicial_escalation.mode", "manual") or "").strip().lower()
    return raw if raw in _VALID_MODES else "manual"


def _delay_days() -> int:
    return max(0, get_int_setting("loans.judicial_escalation.delay_days", 60))


# ---------------------------------------------------------------------------
# Open
# ---------------------------------------------------------------------------


@transaction.atomic
def open_judicial_escalation(
    loan: Loan,
    *,
    motif: str,
    declenche_par=None,
    mode: str = "manual",
) -> JudicialEscalation:
    """Ouvre une escalade judiciaire (idempotente).

    Guards :
      - ``loan.poursuite_judiciaire_at`` doit être posé (R1 a déjà tenté la saisie).
      - ``loan.solde_restant`` doit être > 0 (sinon plus rien à recouvrer).
      - Pas d'escalade existante (OneToOne).

    Retourne l'escalade créée. Si une existait déjà, la renvoie inchangée.
    """
    locked = Loan.objects.select_for_update().get(pk=loan.pk)
    existing = JudicialEscalation.objects.filter(loan=locked).first()
    if existing is not None:
        return existing

    if locked.poursuite_judiciaire_at is None:
        raise ValueError(
            "Impossible d'ouvrir une escalade : la saisie épargne (R1) n'a "
            "pas encore été tentée (poursuite_judiciaire_at est NULL)."
        )
    if Decimal(locked.solde_restant) <= 0:
        raise ValueError(
            "Impossible d'ouvrir une escalade : le crédit n'a plus de reliquat."
        )

    if mode not in _VALID_MODES:
        mode = "manual"

    escalation = JudicialEscalation.objects.create(
        loan=locked,
        statut=JudicialEscalation.Statut.EN_INSTANCE,
        declenche_par=declenche_par,
        declenche_mode=mode,
        motif=(motif or "").strip(),
    )

    record_audit(
        action="loan.judicial_escalation_opened",
        entite_type="Loan",
        entite_id=locked.id,
        user=declenche_par,
        details={
            "escalation_id": escalation.id,
            "mode": mode,
            "solde_restant": str(locked.solde_restant),
            "motif_short": escalation.motif[:140],
        },
    )
    _emit("loan.judicial_escalation_opened", locked, escalation)
    return escalation


# ---------------------------------------------------------------------------
# Décision rendue (phase E)
# ---------------------------------------------------------------------------


@transaction.atomic
def record_judicial_decision(
    escalation: JudicialEscalation,
    *,
    decision_date,
    biens_saisissables: Optional[list] = None,
) -> JudicialEscalation:
    """EN_INSTANCE → DECISION_RENDUE. Idempotent si déjà ``DECISION_RENDUE``."""
    # ``of=("self",)`` : on ne verrouille que la JudicialEscalation. La
    # jointure sur ``loan`` reste un SELECT simple, sinon Postgres refuse
    # le FOR UPDATE sur la nullable side du LEFT OUTER JOIN.
    locked = JudicialEscalation.objects.select_for_update(of=("self",)).select_related(
        "loan"
    ).get(pk=escalation.pk)

    if locked.statut == JudicialEscalation.Statut.DECISION_RENDUE:
        return locked
    if locked.statut != JudicialEscalation.Statut.EN_INSTANCE:
        raise ValueError(
            f"Transition impossible : statut courant '{locked.statut}'."
        )

    locked.statut = JudicialEscalation.Statut.DECISION_RENDUE
    locked.decision_date = decision_date
    locked.biens_saisissables = list(biens_saisissables or [])
    locked.save(
        update_fields=[
            "statut",
            "decision_date",
            "biens_saisissables",
            "updated_at",
        ]
    )

    record_audit(
        action="loan.judicial_decision_recorded",
        entite_type="Loan",
        entite_id=locked.loan_id,
        details={
            "escalation_id": locked.id,
            "decision_date": str(decision_date),
            "nb_biens_saisissables": len(locked.biens_saisissables),
        },
    )
    return locked


# ---------------------------------------------------------------------------
# Exécution
# ---------------------------------------------------------------------------


@transaction.atomic
def record_judicial_execution(
    escalation: JudicialEscalation,
    *,
    execution_date,
    montant_recouvre,
    biens_saisis: Optional[list] = None,
) -> JudicialEscalation:
    """DECISION_RENDUE → EXECUTEE.

    Décrémente ``Loan.solde_restant`` du ``montant_recouvre``. Clôture le
    crédit si le solde tombe à 0. Idempotent — un second appel sur une
    escalade ``EXECUTEE`` est un no-op (les biens/montant sont déjà gravés).
    """
    # ``of=("self",)`` : verrouille uniquement la JudicialEscalation, pas le
    # Loan en jointure. Cohérent avec PG sur les LEFT OUTER JOIN nullable.
    locked = JudicialEscalation.objects.select_for_update(of=("self",)).select_related(
        "loan"
    ).get(pk=escalation.pk)

    if locked.statut == JudicialEscalation.Statut.EXECUTEE:
        return locked
    if locked.statut != JudicialEscalation.Statut.DECISION_RENDUE:
        raise ValueError(
            f"Transition impossible : statut courant '{locked.statut}'. "
            "Une décision doit être enregistrée d'abord."
        )

    recouvre = Decimal(montant_recouvre or 0)
    if recouvre < 0:
        raise ValueError("Le montant recouvré ne peut pas être négatif.")

    loan = Loan.objects.select_for_update().get(pk=locked.loan_id)
    avant = Decimal(loan.solde_restant)
    # On clamp : on ne soustrait jamais plus que le reliquat.
    applique = min(recouvre, avant)
    nouveau = avant - applique
    loan.solde_restant = nouveau
    update_fields = ["solde_restant", "updated_at"]
    closed_loan = False
    if nouveau == 0 and loan.statut != Loan.Statut.CLOTURE:
        loan.statut = Loan.Statut.CLOTURE
        update_fields.append("statut")
        closed_loan = True
    loan.save(update_fields=update_fields)

    now = timezone.now()
    locked.statut = JudicialEscalation.Statut.EXECUTEE
    locked.execution_date = execution_date
    locked.montant_recouvre = applique
    locked.biens_saisis = list(biens_saisis or [])
    locked.closed_at = now
    locked.close_reason = "executee"
    locked.save(
        update_fields=[
            "statut",
            "execution_date",
            "montant_recouvre",
            "biens_saisis",
            "closed_at",
            "close_reason",
            "updated_at",
        ]
    )

    record_audit(
        action="loan.biens_seized",
        entite_type="Loan",
        entite_id=locked.loan_id,
        details={
            "escalation_id": locked.id,
            "execution_date": str(execution_date),
            "montant_recouvre": str(applique),
            "solde_restant_apres": str(nouveau),
            "loan_closed": closed_loan,
            "nb_biens_saisis": len(locked.biens_saisis),
        },
    )
    _emit("loan.biens_seized", loan, locked)
    return locked


# ---------------------------------------------------------------------------
# Classer sans suite
# ---------------------------------------------------------------------------


@transaction.atomic
def classer_sans_suite(
    escalation: JudicialEscalation,
    *,
    motif: str,
) -> JudicialEscalation:
    """Abandon admin (irrécouvrable). Idempotent."""
    locked = JudicialEscalation.objects.select_for_update().get(pk=escalation.pk)
    if locked.statut == JudicialEscalation.Statut.CLASSEE_SANS_SUITE:
        return locked
    if locked.statut not in {
        JudicialEscalation.Statut.EN_INSTANCE,
        JudicialEscalation.Statut.DECISION_RENDUE,
    }:
        raise ValueError(
            f"Transition impossible : statut courant '{locked.statut}'."
        )
    locked.statut = JudicialEscalation.Statut.CLASSEE_SANS_SUITE
    locked.closed_at = timezone.now()
    locked.close_reason = "irrecouvrable"
    # Concatène le motif de classement à la fin du champ motif d'origine.
    locked.motif = (
        f"{locked.motif}\n\n[Classement sans suite] {(motif or '').strip()}"
    )
    locked.save(
        update_fields=["statut", "closed_at", "close_reason", "motif", "updated_at"]
    )
    record_audit(
        action="loan.judicial_classee_sans_suite",
        entite_type="Loan",
        entite_id=locked.loan_id,
        details={"escalation_id": locked.id, "motif": (motif or "")[:140]},
    )
    return locked


# ---------------------------------------------------------------------------
# Cron — auto/hybrid mode
# ---------------------------------------------------------------------------


def auto_escalate_eligible_loans(*, now=None) -> dict:
    """Cron daily — ouvre une escalade pour les Loans éligibles si mode ≠ manual.

    Critères :
      - Mode ``auto`` ou ``hybrid``.
      - ``Loan.poursuite_judiciaire_at < now - delay_days``.
      - ``Loan.solde_restant > 0``.
      - Pas d'escalade existante.

    En mode ``hybrid``, le notif J-N est géré séparément (LOT 14+ wiring) ;
    cette fonction se contente du déclenchement effectif au J0.

    Renvoie ``{"checked": M, "opened": N}``.
    """
    mode = _mode()
    if mode == "manual":
        return {"checked": 0, "opened": 0, "mode": mode}

    now = now or timezone.now()
    cutoff = now - timedelta(days=_delay_days())

    candidates = Loan.objects.filter(
        poursuite_judiciaire_at__lt=cutoff,
        solde_restant__gt=0,
        judicial_escalation__isnull=True,
    )

    opened = 0
    checked = candidates.count()
    for loan in candidates:
        try:
            open_judicial_escalation(
                loan,
                motif=(
                    f"Escalade automatique (mode {mode}) — reliquat "
                    f"{loan.solde_restant} XAF après saisie épargne."
                ),
                declenche_par=None,
                mode=mode,
            )
            opened += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "auto_escalate_eligible_loans — échec loan_id=%s", loan.pk
            )

    return {"checked": checked, "opened": opened, "mode": mode}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _emit(event_code: str, loan: Loan, escalation: JudicialEscalation) -> None:
    """Émission best-effort."""
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            event_code,
            member=loan.member,
            context={
                "prenom": loan.member.prenom,
                "numero_dossier": loan.numero_dossier,
                "solde_restant": str(loan.solde_restant),
                "escalation_statut": escalation.statut,
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "emit_event(%s) a échoué pour loan #%s", event_code, loan.id
        )
