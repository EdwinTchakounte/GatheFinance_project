"""Logique métier des structures employeur & paie (2026-08).

Cagnotte de structure approvisionnée par l'employeur, débitée à chaque paie
(refus si insuffisante). Verser une paie crédite l'épargne classique LIBRE de
l'employé (retirable normalement). Deux modes : lot (toute la structure) ou
individuel. Toutes les mutations passent par ``select_for_update`` + atomicité.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder

from .models import (
    PayrollRun,
    Structure,
    StructureEmployee,
    StructureTransaction,
)


class StructureError(Exception):
    """Erreur métier (cagnotte insuffisante, employé absent, structure close…)."""


def _as_user(by):
    if by is None:
        return None
    return by if getattr(by, "is_authenticated", False) else getattr(by, "user", None)


def _notify(user, *, type, message):
    if user is None:
        return
    try:
        from apps_coop.notifications.services import create_notification

        create_notification(user=user, type=type, message=message, lien="/notifications")
    except Exception:  # noqa: BLE001
        pass


# ── Structure / employés (CRUD) ──────────────────────────────────────────────
def create_structure(*, nom, description="", by=None) -> Structure:
    s = Structure.objects.create(
        nom=nom.strip(), description=(description or "").strip(), created_by=by
    )
    record_audit(
        action="structure.created",
        entite_type="Structure",
        entite_id=s.id,
        user=by,
        details={"nom": s.nom},
    )
    return s


def add_employee(structure, member, *, poste="", attribution="", montant_paie=0, by=None):
    if not structure.is_active:
        raise StructureError("Cette structure est clôturée.")
    row, created = StructureEmployee.objects.get_or_create(
        structure=structure,
        member=member,
        defaults={
            "poste": poste,
            "attribution": attribution,
            "montant_paie": Decimal(montant_paie or 0),
        },
    )
    if not created:
        # Réactive un employé retiré + met à jour ses infos.
        row.actif = True
        row.poste = poste or row.poste
        row.attribution = attribution or row.attribution
        if montant_paie:
            row.montant_paie = Decimal(montant_paie)
        row.save(update_fields=["actif", "poste", "attribution", "montant_paie", "updated_at"])
    record_audit(
        action="structure.employee_added",
        entite_type="StructureEmployee",
        entite_id=row.id,
        user=by,
        details={"structure_id": structure.id, "member_id": member.id},
    )
    return row


def update_employee(employee, *, poste=None, attribution=None, montant_paie=None, by=None):
    fields = []
    if poste is not None:
        employee.poste = poste
        fields.append("poste")
    if attribution is not None:
        employee.attribution = attribution
        fields.append("attribution")
    if montant_paie is not None:
        employee.montant_paie = Decimal(montant_paie)
        fields.append("montant_paie")
    if fields:
        employee.save(update_fields=[*fields, "updated_at"])
    record_audit(
        action="structure.employee_updated",
        entite_type="StructureEmployee",
        entite_id=employee.id,
        user=by,
        details={"champs": fields},
    )
    return employee


def remove_employee(employee, *, by=None):
    """Retire (soft) un employé de la structure — préserve l'historique de paie."""
    employee.actif = False
    employee.save(update_fields=["actif", "updated_at"])
    record_audit(
        action="structure.employee_removed",
        entite_type="StructureEmployee",
        entite_id=employee.id,
        user=by,
        details={"structure_id": employee.structure_id, "member_id": employee.member_id},
    )


def close_structure(structure, *, by=None):
    if not structure.is_active:
        return structure
    structure.statut = Structure.Statut.CLOTUREE
    structure.closed_at = timezone.now()
    structure.save(update_fields=["statut", "closed_at", "updated_at"])
    record_audit(
        action="structure.closed",
        entite_type="Structure",
        entite_id=structure.id,
        user=by,
        details={"nom": structure.nom},
    )
    return structure


# ── Cagnotte : approvisionnement / retrait de fonds ─────────────────────────
def _write_txn(structure, *, type_op, montant, member=None, payroll_run=None,
               payment=None, libelle="", acted_by=None):
    return StructureTransaction.objects.create(
        structure=structure,
        member=member,
        payroll_run=payroll_run,
        payment=payment,
        acted_by=_as_user(acted_by),
        type_op=type_op,
        montant=montant,
        solde_apres=structure.solde,
        date=timezone.now(),
        libelle=libelle,
    )


def fund_structure(*, structure, montant, by=None, libelle="Approvisionnement"):
    """L'employeur approvisionne la cagnotte de la structure."""
    montant = Decimal(montant)
    if montant <= 0:
        raise StructureError("Montant invalide.")
    with db_transaction.atomic():
        s = Structure.objects.select_for_update().get(pk=structure.pk)
        if not s.is_active:
            raise StructureError("Cette structure est clôturée.")
        s.solde = Decimal(s.solde) + montant
        s.save(update_fields=["solde", "updated_at"])
        row = _write_txn(
            s, type_op=StructureTransaction.TypeOp.APPROVISIONNEMENT,
            montant=montant, libelle=libelle, acted_by=by,
        )
    record_audit(
        action="structure.funded",
        entite_type="StructureTransaction",
        entite_id=row.id,
        user=by,
        details={"structure_id": structure.id, "montant": str(montant)},
    )
    return row


def withdraw_funds(*, structure, montant, by=None):
    """Retrait de fonds de la cagnotte (restitution employeur)."""
    montant = Decimal(montant)
    if montant <= 0:
        raise StructureError("Montant invalide.")
    with db_transaction.atomic():
        s = Structure.objects.select_for_update().get(pk=structure.pk)
        if Decimal(s.solde) < montant:
            raise StructureError(
                f"Cagnotte insuffisante ({int(s.solde)} XAF disponibles)."
            )
        s.solde = Decimal(s.solde) - montant
        s.save(update_fields=["solde", "updated_at"])
        row = _write_txn(
            s, type_op=StructureTransaction.TypeOp.RETRAIT_FONDS,
            montant=montant, libelle="Retrait de fonds", acted_by=by,
        )
    record_audit(
        action="structure.funds_withdrawn",
        entite_type="StructureTransaction",
        entite_id=row.id,
        user=by,
        details={"structure_id": structure.id, "montant": str(montant)},
    )
    return row


# ── Crédit de l'épargne classique LIBRE d'un membre ─────────────────────────
def _credit_member_classic(member, montant):
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    ClassicSavingsAccount.objects.get_or_create(
        member=member, defaults={"date_ouverture": timezone.localdate()}
    )
    account = ClassicSavingsAccount.objects.select_for_update().get(member=member)
    account.solde = Decimal(account.solde) + Decimal(montant)
    account.save(update_fields=["solde", "updated_at"])
    ClassicSavingsTransaction.objects.create(
        account=account,
        type_op=ClassicSavingsTransaction.TypeOp.DEPOT,
        montant=montant,
        solde_apres=account.solde,
        date=timezone.now(),
        booklet_order=BookletOrder.latest_for(member),
    )


# ── Paie : lot (toute la structure) ou individuel ───────────────────────────
def pay_employee(*, structure, employee, montant=None, by=None):
    """Verse la paie d'UN employé dans son épargne classique libre (débite la
    cagnotte). ``montant`` par défaut = salaire de l'employé."""
    montant = Decimal(montant) if montant is not None else Decimal(employee.montant_paie)
    if montant <= 0:
        raise StructureError("Montant de paie invalide.")
    with db_transaction.atomic():
        s = Structure.objects.select_for_update().get(pk=structure.pk)
        if not s.is_active:
            raise StructureError("Cette structure est clôturée.")
        if Decimal(s.solde) < montant:
            raise StructureError(
                f"Cagnotte insuffisante ({int(s.solde)} XAF) pour cette paie."
            )
        s.solde = Decimal(s.solde) - montant
        s.save(update_fields=["solde", "updated_at"])
        _credit_member_classic(employee.member, montant)
        row = _write_txn(
            s, type_op=StructureTransaction.TypeOp.VERSEMENT_PAIE,
            montant=montant, member=employee.member,
            libelle=f"Paie {employee.member.numero_membre}", acted_by=by,
        )
    record_audit(
        action="structure.salary_paid",
        entite_type="StructureTransaction",
        entite_id=row.id,
        user=by,
        details={"structure_id": structure.id, "member_id": employee.member_id,
                 "montant": str(montant)},
    )
    _notify(
        getattr(employee.member, "user", None),
        type="structure.paie",
        message=(
            f"Ton salaire de {int(montant)} FCFA a été versé par « {s.nom} » "
            f"sur ton épargne libre."
        ),
    )
    return row


def run_payroll(*, structure, periode, by=None):
    """Lot de paie : verse le salaire de TOUS les employés actifs. Atomique — si
    la cagnotte ne couvre pas le TOTAL, rien n'est versé."""
    with db_transaction.atomic():
        s = Structure.objects.select_for_update().get(pk=structure.pk)
        if not s.is_active:
            raise StructureError("Cette structure est clôturée.")
        employees = list(
            StructureEmployee.objects.filter(
                structure=s, actif=True, montant_paie__gt=0
            ).select_related("member")
        )
        if not employees:
            raise StructureError("Aucun employé actif avec un salaire à verser.")
        total = sum((Decimal(e.montant_paie) for e in employees), Decimal("0"))
        if Decimal(s.solde) < total:
            raise StructureError(
                f"Cagnotte insuffisante : {int(total)} XAF requis, "
                f"{int(s.solde)} XAF disponibles."
            )
        run = PayrollRun.objects.create(
            structure=s, periode=(periode or "").strip() or "Paie",
            total_verse=total, employes_count=len(employees),
            created_by=by,
        )
        for e in employees:
            montant = Decimal(e.montant_paie)
            s.solde = Decimal(s.solde) - montant
            s.save(update_fields=["solde", "updated_at"])
            _credit_member_classic(e.member, montant)
            _write_txn(
                s, type_op=StructureTransaction.TypeOp.VERSEMENT_PAIE,
                montant=montant, member=e.member, payroll_run=run,
                libelle=f"Paie {run.periode} · {e.member.numero_membre}",
                acted_by=by,
            )
    record_audit(
        action="structure.payroll_run",
        entite_type="PayrollRun",
        entite_id=run.id,
        user=by,
        details={"structure_id": structure.id, "periode": run.periode,
                 "total": str(total), "employes": len(employees)},
    )
    # Notifie chaque employé payé.
    for e in employees:
        _notify(
            getattr(e.member, "user", None),
            type="structure.paie",
            message=(
                f"Ton salaire de {int(e.montant_paie)} FCFA ({run.periode}) a été "
                f"versé par « {structure.nom} » sur ton épargne libre."
            ),
        )
    return run
