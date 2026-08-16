"""Logique métier des collectes particulières (par cycles).

Regroupe : gestion des cycles (ouvrir / clôturer / cycle courant), demande de
participation (rattachée au cycle ouvert), décision admin, crédit d'un versement
Mobile Money (hook paiement) et transfert depuis l'épargne classique.

Principes : 1 seul cycle ouvert par type ; re-demande à chaque cycle ; clôture =
gel + archivage (aucun mouvement d'argent automatique). Les mutations de solde
passent par ``select_for_update`` et écrivent un ledger append-only.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)


class SpecialCollectionError(Exception):
    """Erreur métier (pas de cycle ouvert, participation existante, solde…)."""


# ── Cycles ────────────────────────────────────────────────────────────────────
def current_open_cycle(type: str) -> SpecialCollectionCycle | None:
    """Le cycle actuellement ouvert pour ``type``, ou ``None``."""
    return SpecialCollectionCycle.objects.filter(
        type=type, statut=SpecialCollectionCycle.Statut.OUVERT
    ).first()


def open_cycle(
    *, type: str, nom: str, date_debut=None, date_fin=None, by=None
) -> SpecialCollectionCycle:
    """Ouvre un nouveau cycle pour ``type`` (clôt automatiquement le précédent).

    Le cycle précédent est **gelé + archivé** (statut ``clos``) : ses soldes ne
    bougent plus. Les participants devront re-demander pour le nouveau cycle.
    """
    if type not in SpecialCollectionMembership.Type.values:
        raise SpecialCollectionError("Type de collecte inconnu.")

    with db_transaction.atomic():
        prev = (
            SpecialCollectionCycle.objects.select_for_update()
            .filter(type=type, statut=SpecialCollectionCycle.Statut.OUVERT)
            .first()
        )
        if prev is not None:
            _close(prev, by=by)

        cycle = SpecialCollectionCycle.objects.create(
            type=type,
            nom=nom.strip(),
            date_debut=date_debut or timezone.now().date(),
            date_fin=date_fin,
            statut=SpecialCollectionCycle.Statut.OUVERT,
            created_by=by,
        )

    record_audit(
        action="special_collection.cycle_opened",
        entite_type="SpecialCollectionCycle",
        entite_id=cycle.id,
        user=by,
        details={"type": type, "nom": cycle.nom, "closed_previous": bool(prev)},
    )
    return cycle


def close_cycle(cycle: SpecialCollectionCycle, *, by=None) -> SpecialCollectionCycle:
    """Clôture manuelle d'un cycle (gel + archivage)."""
    if not cycle.is_open:
        return cycle
    _close(cycle, by=by)
    record_audit(
        action="special_collection.cycle_closed",
        entite_type="SpecialCollectionCycle",
        entite_id=cycle.id,
        user=by,
        details={"type": cycle.type, "nom": cycle.nom},
    )
    return cycle


def _close(cycle: SpecialCollectionCycle, *, by=None) -> None:
    cycle.statut = SpecialCollectionCycle.Statut.CLOS
    cycle.closed_at = timezone.now()
    cycle.closed_by = by
    cycle.save(update_fields=["statut", "closed_at", "closed_by", "updated_at"])


# ── Demande de participation (dans le cycle ouvert) ──────────────────────────
def request_participation(
    *, member, type: str, objectif: str, montant_cible=None, form_payload=None
) -> SpecialCollectionMembership:
    """Crée (ou ré-arme) une demande de participation pour le CYCLE OUVERT.

    Lève s'il n'y a pas de cycle ouvert pour ce type. Refuse une seconde demande
    tant qu'une participation existe déjà (en attente / validée) pour ce cycle ;
    une participation *rejetée* dans ce cycle peut être re-soumise.
    """
    if type not in SpecialCollectionMembership.Type.values:
        raise SpecialCollectionError("Type de collecte inconnu.")

    cycle = current_open_cycle(type)
    if cycle is None:
        raise SpecialCollectionError(
            "Aucun cycle ouvert pour cette collecte. Reviens quand la "
            "coopérative aura lancé un nouveau cycle."
        )

    existing = SpecialCollectionMembership.objects.filter(
        member=member, cycle=cycle
    ).first()
    if existing and existing.statut in (
        SpecialCollectionMembership.Statut.EN_ATTENTE,
        SpecialCollectionMembership.Statut.VALIDE,
    ):
        raise SpecialCollectionError(
            "Une demande est déjà en cours ou validée pour ce cycle."
        )

    payload = form_payload or {}
    if existing:
        existing.statut = SpecialCollectionMembership.Statut.EN_ATTENTE
        existing.objectif = objectif
        existing.montant_cible = montant_cible
        existing.form_payload = payload
        existing.motif_rejet = ""
        existing.validated_by = None
        existing.validated_at = None
        existing.save()
        membership = existing
    else:
        membership = SpecialCollectionMembership.objects.create(
            member=member,
            cycle=cycle,
            type=type,
            statut=SpecialCollectionMembership.Statut.EN_ATTENTE,
            objectif=objectif,
            montant_cible=montant_cible,
            form_payload=payload,
        )

    record_audit(
        action="special_collection.requested",
        entite_type="SpecialCollectionMembership",
        entite_id=membership.id,
        details={"member_id": member.id, "type": type, "cycle_id": cycle.id},
    )
    return membership


# ── Décision admin ────────────────────────────────────────────────────────────
def validate_participation(membership: SpecialCollectionMembership, *, by=None):
    membership.statut = SpecialCollectionMembership.Statut.VALIDE
    membership.motif_rejet = ""
    membership.validated_by = by
    membership.validated_at = timezone.now()
    membership.save(
        update_fields=["statut", "motif_rejet", "validated_by", "validated_at", "updated_at"]
    )
    record_audit(
        action="special_collection.validated",
        entite_type="SpecialCollectionMembership",
        entite_id=membership.id,
        user=by,
        details={"member_id": membership.member_id, "type": membership.type},
    )
    return membership


def reject_participation(membership: SpecialCollectionMembership, *, motif: str, by=None):
    membership.statut = SpecialCollectionMembership.Statut.REJETE
    membership.motif_rejet = motif or ""
    membership.validated_by = by
    membership.validated_at = timezone.now()
    membership.save(
        update_fields=["statut", "motif_rejet", "validated_by", "validated_at", "updated_at"]
    )
    record_audit(
        action="special_collection.rejected",
        entite_type="SpecialCollectionMembership",
        entite_id=membership.id,
        user=by,
        details={"member_id": membership.member_id, "type": membership.type, "motif": motif},
    )
    return membership


def _active_membership_for(member, type: str):
    """Participation VALIDÉE du membre dans le cycle OUVERT de ``type``."""
    cycle = current_open_cycle(type)
    if cycle is None:
        return None
    return (
        SpecialCollectionMembership.objects.select_for_update()
        .filter(member=member, cycle=cycle)
        .first()
    )


# ── Crédit d'un versement (appelé par le hook paiement) ───────────────────────
def credit_versement(payment) -> SpecialCollectionTransaction:
    """Crédite la collecte du membre (cycle ouvert) suite à un versement validé.

    Doit tourner dans la transaction du webhook/cash-in. Lève si pas de
    participation validée dans le cycle ouvert (défense en profondeur ;
    `payments/init` le garantit déjà).
    """
    membership = _active_membership_for(payment.member, payment.type)
    if membership is None or not membership.is_active:
        raise SpecialCollectionError(
            "Aucune participation validée dans le cycle ouvert de cette collecte."
        )

    nouveau_solde = Decimal(membership.solde) + Decimal(payment.montant)
    membership.solde = nouveau_solde
    membership.save(update_fields=["solde", "updated_at"])

    row = SpecialCollectionTransaction.objects.create(
        membership=membership,
        payment=payment,
        type_op=SpecialCollectionTransaction.TypeOp.VERSEMENT,
        montant=payment.montant,
        solde_apres=nouveau_solde,
        libelle="Versement Mobile Money",
    )
    record_audit(
        action="special_collection.deposit",
        entite_type="SpecialCollectionTransaction",
        entite_id=row.id,
        details={
            "member_id": payment.member_id,
            "type": payment.type,
            "cycle_id": membership.cycle_id,
            "montant": str(payment.montant),
            "solde_apres": str(nouveau_solde),
        },
    )
    return row


# ── Transfert interne depuis l'épargne classique disponible ───────────────────
def transfer_from_classic(*, member, type: str, montant) -> SpecialCollectionTransaction:
    """Transfère ``montant`` de l'épargne classique LIBRE vers la collecte
    (cycle ouvert). Atomique : débite l'épargne classique, crédite la collecte.
    """
    from apps_coop.savings.models import ClassicSavingsAccount, ClassicSavingsTransaction

    montant = Decimal(montant)
    if montant <= 0:
        raise SpecialCollectionError("Montant invalide.")

    with db_transaction.atomic():
        membership = _active_membership_for(member, type)
        if membership is None or not membership.is_active:
            raise SpecialCollectionError(
                "Participation non validée dans le cycle ouvert de cette collecte."
            )

        account = (
            ClassicSavingsAccount.objects.select_for_update()
            .filter(member=member)
            .first()
        )
        disponible = Decimal(account.solde_libre) if account else Decimal("0")
        if account is None or disponible < montant:
            raise SpecialCollectionError(
                "Épargne classique disponible insuffisante pour ce transfert."
            )

        account.solde = Decimal(account.solde) - montant
        account.save(update_fields=["solde", "updated_at"])
        ClassicSavingsTransaction.objects.create(
            account=account,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=montant,
            solde_apres=account.solde,
            date=timezone.now(),
        )

        nouveau_solde = Decimal(membership.solde) + montant
        membership.solde = nouveau_solde
        membership.save(update_fields=["solde", "updated_at"])
        row = SpecialCollectionTransaction.objects.create(
            membership=membership,
            type_op=SpecialCollectionTransaction.TypeOp.TRANSFERT,
            montant=montant,
            solde_apres=nouveau_solde,
            libelle="Transfert depuis épargne classique",
        )

    record_audit(
        action="special_collection.transfer_in",
        entite_type="SpecialCollectionTransaction",
        entite_id=row.id,
        details={
            "member_id": member.id,
            "type": type,
            "cycle_id": membership.cycle_id,
            "montant": str(montant),
            "solde_apres": str(nouveau_solde),
        },
    )
    return row
