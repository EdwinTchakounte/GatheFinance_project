"""Logique métier des collectes particulières.

Regroupe : demande de participation, décision admin (valider / rejeter),
crédit d'un versement Mobile Money (appelé par le hook paiement) et transfert
interne depuis l'épargne classique disponible.

Toutes les mutations de solde passent par ``select_for_update`` pour sérialiser
les opérations concurrentes, et écrivent une ligne de ledger append-only.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit

from .models import SpecialCollectionMembership, SpecialCollectionTransaction


class SpecialCollectionError(Exception):
    """Erreur métier (participation déjà existante, solde insuffisant, etc.)."""


# ── Demande de participation ──────────────────────────────────────────────────
def request_participation(
    *, member, type: str, objectif: str, montant_cible=None, form_payload=None
) -> SpecialCollectionMembership:
    """Crée (ou ré-ouvre) une demande de participation en attente.

    Refuse une seconde demande tant qu'une participation existe déjà en attente
    ou validée. Une participation *rejetée* peut être re-soumise (on ré-arme la
    même ligne en ``en_attente``).
    """
    if type not in SpecialCollectionMembership.Type.values:
        raise SpecialCollectionError("Type de collecte inconnu.")

    existing = SpecialCollectionMembership.objects.filter(
        member=member, type=type
    ).first()
    if existing and existing.statut in (
        SpecialCollectionMembership.Statut.EN_ATTENTE,
        SpecialCollectionMembership.Statut.VALIDE,
    ):
        raise SpecialCollectionError(
            "Une demande est déjà en cours ou validée pour cette collecte."
        )

    payload = form_payload or {}
    if existing:
        # Ré-soumission après rejet : on repart d'une demande propre.
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
        details={"member_id": member.id, "type": type},
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


# ── Crédit d'un versement (appelé par le hook paiement) ───────────────────────
def credit_versement(payment) -> SpecialCollectionTransaction:
    """Crédite le solde de la collecte du membre suite à un versement validé.

    Doit tourner dans la transaction du webhook/cash-in. Lève si le membre n'a
    pas de participation VALIDÉE (le point d'entrée `payments/init` en garantit
    une, ce garde est une défense en profondeur).
    """
    membership = (
        SpecialCollectionMembership.objects.select_for_update()
        .filter(member=payment.member, type=payment.type)
        .first()
    )
    if membership is None or not membership.is_active:
        raise SpecialCollectionError(
            "Aucune participation validée pour cette collecte particulière."
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
            "montant": str(payment.montant),
            "solde_apres": str(nouveau_solde),
        },
    )
    return row


# ── Transfert interne depuis l'épargne classique disponible ───────────────────
def transfer_from_classic(*, member, type: str, montant) -> SpecialCollectionTransaction:
    """Transfère ``montant`` de l'épargne classique LIBRE vers la collecte.

    Atomique : débite le compte épargne classique (part librement retirable) et
    crédite la collecte, avec une écriture de chaque côté.
    """
    from apps_coop.savings.models import ClassicSavingsAccount, ClassicSavingsTransaction

    montant = Decimal(montant)
    if montant <= 0:
        raise SpecialCollectionError("Montant invalide.")

    with db_transaction.atomic():
        membership = (
            SpecialCollectionMembership.objects.select_for_update()
            .filter(member=member, type=type)
            .first()
        )
        if membership is None or not membership.is_active:
            raise SpecialCollectionError(
                "Participation non validée pour cette collecte particulière."
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

        # Débit épargne classique (part libre).
        account.solde = Decimal(account.solde) - montant
        account.save(update_fields=["solde", "updated_at"])
        ClassicSavingsTransaction.objects.create(
            account=account,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=montant,
            solde_apres=account.solde,
            date=timezone.now(),
        )

        # Crédit collecte particulière.
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
            "montant": str(montant),
            "solde_apres": str(nouveau_solde),
        },
    )
    return row
