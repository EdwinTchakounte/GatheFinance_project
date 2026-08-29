"""Logique métier des collectes particulières (par cycles).

Regroupe : gestion des cycles (ouvrir / clôturer / cycle courant), demande de
participation (rattachée au cycle ouvert), décision admin, crédit d'un versement
Mobile Money (hook paiement) et transfert depuis l'épargne classique.

Principes : PLUSIEURS collectes ouvertes par type possibles ; chaque
participation/versement vise un cycle PRÉCIS ; verser exige d'avoir acheté le
carnet du type (tontine/caisse) et un montant ≥ plancher du cycle ; clôture =
gel + archivage (aucun mouvement d'argent automatique). Les mutations de solde
passent par ``select_for_update`` et écrivent un ledger append-only.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder

from .models import (
    SpecialCollectionCycle,
    SpecialCollectionMembership,
    SpecialCollectionTransaction,
)


class SpecialCollectionError(Exception):
    """Erreur métier (cycle clos, participation existante, carnet manquant…)."""


# Type de collecte → type de carnet requis pour y verser (carnet par type).
CARNET_TYPE_FOR_COLLECTION = {
    SpecialCollectionMembership.Type.TONTINE_ALIMENTAIRE: "tontine",
    SpecialCollectionMembership.Type.CAISSE_SCOLAIRE: "caisse_scolaire",
}


def member_carnet_for(member, collection_type: str):
    """Carnet (BookletOrder) du membre pour ce type de collecte, ou ``None``.

    Verser dans une tontine/caisse exige d'avoir d'abord acheté le carnet du
    type correspondant (décision 2026-08 : un carnet par type).
    """
    from apps_coop.members.models import BookletOrder

    carnet_type = CARNET_TYPE_FOR_COLLECTION.get(collection_type)
    if carnet_type is None:
        return None
    return BookletOrder.latest_for(member, carnet_type)


def _ensure_carnet_and_floor(member, cycle, membership, montant) -> None:
    """Barrière commune aux versements/transferts d'une collecte :

    1. le membre doit posséder le carnet du type (tontine/caisse) ;
    2. le montant doit être ≥ plancher par versement de la collecte.
    Lève ``SpecialCollectionError`` sinon.
    """
    if member_carnet_for(member, membership.type) is None:
        raise SpecialCollectionError(
            "Tu dois d'abord acheter le carnet de cette collecte avant de "
            "pouvoir verser."
        )
    plancher = Decimal(cycle.montant_minimal or 0)
    if plancher > 0 and Decimal(montant) < plancher:
        raise SpecialCollectionError(
            f"Le versement minimal pour cette collecte est de {int(plancher)} "
            f"FCFA."
        )


# ── Cycles ────────────────────────────────────────────────────────────────────
def open_cycles(type: str):
    """Toutes les collectes OUVERTES pour ``type`` (plusieurs possibles)."""
    return SpecialCollectionCycle.objects.filter(
        type=type, statut=SpecialCollectionCycle.Statut.OUVERT
    ).order_by("-date_debut", "-id")


def current_open_cycle(type: str) -> SpecialCollectionCycle | None:
    """La collecte ouverte la plus récente pour ``type`` (compat), ou ``None``.

    Conservé pour les appelants legacy. Avec plusieurs collectes ouvertes,
    préférer un ``cycle_id`` explicite (cf. ``open_cycles``).
    """
    return open_cycles(type).first()


def open_cycle(
    *,
    type: str,
    nom: str,
    date_debut=None,
    date_fin=None,
    montant_minimal=None,
    description: str = "",
    by=None,
) -> SpecialCollectionCycle:
    """Ouvre une nouvelle collecte pour ``type``.

    2026-08 : n'clôt PLUS le cycle précédent — plusieurs collectes du même type
    peuvent coexister ouvertes. L'admin fixe le titre (``nom``), le plancher par
    versement (``montant_minimal``) et une description libre.
    """
    if type not in SpecialCollectionMembership.Type.values:
        raise SpecialCollectionError("Type de collecte inconnu.")

    cycle = SpecialCollectionCycle.objects.create(
        type=type,
        nom=nom.strip(),
        description=(description or "").strip(),
        montant_minimal=montant_minimal or Decimal("0"),
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
        details={
            "type": type,
            "nom": cycle.nom,
            "montant_minimal": str(cycle.montant_minimal),
        },
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


# ── Demande de participation (dans une collecte ouverte précise) ─────────────
def _resolve_open_cycle(*, type: str, cycle_id=None) -> SpecialCollectionCycle:
    """Résout la collecte ouverte ciblée.

    Avec plusieurs collectes ouvertes par type, ``cycle_id`` est attendu. Par
    compat, s'il est omis on prend la plus récente ouverte (utile quand une
    seule existe). Lève si rien d'ouvert / cycle clos / mauvais type.
    """
    if type not in SpecialCollectionMembership.Type.values:
        raise SpecialCollectionError("Type de collecte inconnu.")

    if cycle_id is not None:
        cycle = SpecialCollectionCycle.objects.filter(pk=cycle_id, type=type).first()
        if cycle is None:
            raise SpecialCollectionError("Collecte introuvable.")
        if not cycle.is_open:
            raise SpecialCollectionError("Cette collecte est clôturée.")
        return cycle

    cycle = current_open_cycle(type)
    if cycle is None:
        raise SpecialCollectionError(
            "Aucune collecte ouverte pour ce type. Reviens quand la "
            "coopérative en aura lancé une."
        )
    return cycle


def request_participation(
    *, member, type: str, objectif: str, montant_cible=None, form_payload=None,
    cycle_id=None,
) -> SpecialCollectionMembership:
    """Crée (ou ré-arme) une demande de participation pour une collecte ouverte
    précise (``cycle_id``).

    Refuse une seconde demande tant qu'une participation existe déjà (en attente
    / validée) pour cette collecte ; une participation *rejetée* peut être
    re-soumise. Un membre peut participer à PLUSIEURS collectes du même type
    (une participation par collecte).
    """
    cycle = _resolve_open_cycle(type=type, cycle_id=cycle_id)

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


def _membership_in_cycle(member, cycle):
    """Participation du membre dans une collecte précise (verrouillée)."""
    return (
        SpecialCollectionMembership.objects.select_for_update()
        .filter(member=member, cycle=cycle)
        .first()
    )


# ── Crédit d'un versement (appelé par le hook paiement) ───────────────────────
def credit_versement(payment) -> SpecialCollectionTransaction:
    """Crédite la collecte ciblée par le paiement (``payment.special_cycle``).

    Doit tourner dans la transaction du webhook/cash-in. Défense en profondeur
    (`payments/init` garantit déjà participation validée + carnet + plancher) :
    lève si la participation n'est pas active dans la collecte visée.
    """
    cycle = payment.special_cycle
    if cycle is None:
        # Rétro-compat : un paiement caisse/tontine initié AVANT l'ajout de
        # `special_cycle` (déployé pendant qu'il était en attente) n'a pas de
        # cycle cible → on retombe sur le cycle ouvert courant du type plutôt
        # que de bloquer le webhook (sinon versement débité mais jamais crédité).
        cycle = current_open_cycle(payment.type)
    if cycle is None:
        raise SpecialCollectionError(
            "Aucune collecte ouverte pour imputer ce versement."
        )
    membership = _membership_in_cycle(payment.member, cycle)
    if membership is None or not membership.is_active:
        raise SpecialCollectionError(
            "Aucune participation validée dans cette collecte."
        )

    nouveau_solde = Decimal(membership.solde) + Decimal(payment.montant)
    membership.solde = nouveau_solde
    membership.save(update_fields=["solde", "updated_at"])

    # Provenance : un cash-in agence (source manuel) est étiqueté « manuel »,
    # un versement entrant Mobile Money « versement ».
    is_manual = payment.source == payment.Source.MANUEL
    row = SpecialCollectionTransaction.objects.create(
        membership=membership,
        payment=payment,
        booklet_order=member_carnet_for(payment.member, membership.type),
        type_op=(
            SpecialCollectionTransaction.TypeOp.MANUEL
            if is_manual
            else SpecialCollectionTransaction.TypeOp.VERSEMENT
        ),
        montant=payment.montant,
        solde_apres=nouveau_solde,
        date=payment.date_versement,
        libelle="Versement agence" if is_manual else "Versement Mobile Money",
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
def transfer_from_classic(
    *, member, type: str, montant, cycle_id=None
) -> SpecialCollectionTransaction:
    """Transfère ``montant`` de l'épargne classique LIBRE vers une collecte
    ouverte précise (``cycle_id``). Atomique : débite l'épargne classique,
    crédite la collecte. Exige carnet du type + montant ≥ plancher de la collecte.
    """
    from apps_coop.savings.models import ClassicSavingsAccount, ClassicSavingsTransaction

    montant = Decimal(montant)
    if montant <= 0:
        raise SpecialCollectionError("Montant invalide.")

    with db_transaction.atomic():
        cycle = _resolve_open_cycle(type=type, cycle_id=cycle_id)
        membership = _membership_in_cycle(member, cycle)
        if membership is None or not membership.is_active:
            raise SpecialCollectionError(
                "Participation non validée dans cette collecte."
            )
        _ensure_carnet_and_floor(member, cycle, membership, montant)

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
            booklet_order=BookletOrder.latest_for(member),
        )

        nouveau_solde = Decimal(membership.solde) + montant
        membership.solde = nouveau_solde
        membership.save(update_fields=["solde", "updated_at"])
        row = SpecialCollectionTransaction.objects.create(
            membership=membership,
            booklet_order=member_carnet_for(member, membership.type),
            type_op=SpecialCollectionTransaction.TypeOp.TRANSFERT,
            montant=montant,
            solde_apres=nouveau_solde,
            date=timezone.now(),
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


def decaisser_participation(
    *, member, cycle_id, montant, destination="epargne", note="", by=None
) -> SpecialCollectionTransaction:
    """Décaissement d'un participant caisse/tontine : DÉBITE son solde et sort
    réellement l'argent.

    ``destination`` :
      * ``"epargne"`` → crédite l'épargne classique LIBRE du membre (retirable) ;
      * ``"cash"``    → remise en espèces à l'agence (aucun autre crédit).

    Autorisé même sur un cycle clos (restitution). Refuse un montant > solde.
    L'écriture RETRAIT est rattachée au carnet du type (caisse / tontine).
    """
    montant = Decimal(montant)
    if montant <= 0:
        raise SpecialCollectionError("Le montant doit être strictement positif.")
    if destination not in ("epargne", "cash"):
        raise SpecialCollectionError("Destination inconnue (epargne / cash).")

    with db_transaction.atomic():
        cycle = SpecialCollectionCycle.objects.filter(pk=cycle_id).first()
        if cycle is None:
            raise SpecialCollectionError("Collecte introuvable.")
        membership = (
            SpecialCollectionMembership.objects.select_for_update()
            .filter(member=member, cycle=cycle)
            .first()
        )
        if membership is None:
            raise SpecialCollectionError(
                "Ce membre ne participe pas à cette collecte."
            )
        solde = Decimal(membership.solde)
        if montant > solde:
            raise SpecialCollectionError(
                f"Montant supérieur au solde de la collecte ({int(solde)} XAF)."
            )

        nouveau_solde = solde - montant
        membership.solde = nouveau_solde
        membership.save(update_fields=["solde", "updated_at"])

        libelle = (
            "Décaissement vers épargne"
            if destination == "epargne"
            else "Décaissement espèces (agence)"
        )
        if note:
            libelle += f" — {note.strip()[:80]}"
        row = SpecialCollectionTransaction.objects.create(
            membership=membership,
            payment=None,
            booklet_order=member_carnet_for(member, membership.type),
            type_op=SpecialCollectionTransaction.TypeOp.RETRAIT,
            montant=montant,
            solde_apres=nouveau_solde,
            date=timezone.now(),
            libelle=libelle,
        )

        if destination == "epargne":
            # Crédite l'épargne classique du membre (réutilise l'helper des
            # tontines de groupe : écriture DEPOT rattachée au carnet).
            from apps_coop.special_collections.group_services import (
                _credit_member_classic,
            )

            _credit_member_classic(
                member, montant, libelle=f"Décaissement {cycle.nom}"
            )

        record_audit(
            action="special_collection.decaissement",
            entite_type="SpecialCollectionTransaction",
            entite_id=row.id,
            user=by,
            details={
                "member_id": member.id,
                "cycle_id": cycle.id,
                "montant": str(montant),
                "destination": destination,
                "solde_apres": str(nouveau_solde),
            },
        )
    return row
