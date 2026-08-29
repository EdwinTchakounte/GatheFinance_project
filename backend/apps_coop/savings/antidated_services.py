"""Écritures antidatées — reprise d'historique des carnets papier.

Contexte : certains membres détiennent déjà un carnet papier (versements /
retraits) pour l'année en cours. On veut ressaisir cet historique en base, à sa
**vraie date**, pour que le solde applicatif rejoigne le solde du carnet.

Décision métier (gelée) : **reprise d'historique seule**. Une écriture antidatée
est enregistrée telle quelle et ne déclenche AUCUN traitement :

  * pas de clôture mensuelle rejouée (ni commission 1 %, ni restitution) — les
    clôtures passées ont déjà eu lieu physiquement à l'agence, les rejouer
    prélèverait la commission une seconde fois ;
  * pas de ``Payment`` (aucun encaissement réel ne se produit maintenant) ;
  * pas de notification au membre (on reconstruit un passé qu'il connaît déjà).

Le seul effet est comptable : la ligne de grand livre est créée à sa date, et le
solde du compte est ajusté du montant. L'invariant visé est simple —
**somme des écritures = solde du carnet papier**.

Rattachement au carnet : chaque écriture pointe vers le carnet **actif à sa
date** (``BookletOrder.for_member_at``), pas le plus récent.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder, Member

from .models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)


logger = logging.getLogger(__name__)


PRODUCT_COLLECTE = "collecte"
PRODUCT_CLASSIQUE = "classique"
PRODUCT_TONTINE = "tontine"
PRODUCT_CAISSE = "caisse_scolaire"
SENS_DEPOT = "depot"
SENS_RETRAIT = "retrait"

# Produits « collecte particulière » antidatables → type de collecte + type de
# carnet requis pour l'imputation.
_SPECIAL_PRODUCTS = {
    PRODUCT_TONTINE: "tontine_alimentaire",
    PRODUCT_CAISSE: "caisse_scolaire",
}


class AntidatedEntryError(ValueError):
    """Saisie antidatée invalide (message lisible par l'agent)."""


@dataclass
class AntidatedBookletResult:
    booklet_order_id: int
    payment_id: int
    date: datetime
    annee: int


@dataclass
class AntidatedResult:
    transaction_id: int
    product: str
    sens: str
    montant: Decimal
    date: datetime
    solde_apres: Decimal
    booklet_order_id: int | None


def _as_aware(d) -> datetime:
    """Normalise une date/datetime en ``datetime`` aware à midi (jour métier)."""
    if isinstance(d, datetime):
        dt = d
    else:
        dt = datetime.combine(d, time(12, 0))
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@transaction.atomic
def create_antidated_booklet(
    *,
    member: Member,
    date_op,
    montant: Decimal = Decimal("0"),
    annee: int | None = None,
    note: str = "",
    recorded_by=None,
) -> AntidatedBookletResult:
    """Crée un **carnet antidaté** (reprise d'un carnet papier existant).

    Un ``BookletOrder`` exige un ``Payment`` (schéma : OneToOne obligatoire). On
    crée donc les deux directement, datés dans le passé, **sans passer par le
    hook** ``_hook_carnet_fees`` (qui créerait un second carnet et pourrait
    déclencher un renouvellement d'adhésion). Le carnet est marqué ``DELIVREE``
    puisqu'il est déjà, physiquement, entre les mains du membre.

    ``montant`` par défaut 0 : le carnet existe déjà, on ne ré-encaisse pas de
    frais et on ne veut pas gonfler les KPI de recettes. L'agent peut passer un
    montant s'il veut tracer les frais réellement perçus à l'époque.

    Les écritures antidatées postérieures à ``date_op`` se rattacheront à ce
    carnet via ``BookletOrder.for_member_at``.
    """
    from apps_coop.payments.models import Payment

    date_dt = _as_aware(date_op)
    op_day = date_dt.date()
    today = timezone.localdate()
    if op_day > today:
        raise AntidatedEntryError(
            "Un carnet antidaté ne peut pas être créé dans le futur."
        )

    montant = Decimal(montant or 0)
    if montant < 0:
        raise AntidatedEntryError("Le montant du carnet ne peut être négatif.")

    payment = Payment.objects.create(
        member=member,
        montant=montant,
        type=Payment.Type.FRAIS_CARNET,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=date_dt,
        date_validation=date_dt,
        validated_by=recorded_by,
        reference_externe="reprise-historique",
    )
    booklet = BookletOrder.objects.create(
        member=member,
        payment=payment,
        statut=BookletOrder.Statut.DELIVREE,
        annee=annee or op_day.year,
        date_delivrance=date_dt,
        notes_agence=(f"Carnet antidaté (reprise historique). {note}").strip()[:2000],
    )
    # created_at est auto_now_add : on le backdate pour que for_member_at /
    # latest_for ordonnent correctement ce carnet dans l'historique.
    BookletOrder.objects.filter(id=booklet.id).update(created_at=date_dt)
    booklet.refresh_from_db()

    record_audit(
        action="savings.antidated_booklet_created",
        entite_type="BookletOrder",
        entite_id=booklet.id,
        user=recorded_by,
        details={
            "member_id": member.id,
            "payment_id": payment.id,
            "date": op_day.isoformat(),
            "annee": booklet.annee,
            "montant": str(montant),
            "note": note.strip()[:500],
        },
    )

    return AntidatedBookletResult(
        booklet_order_id=booklet.id,
        payment_id=payment.id,
        date=date_dt,
        annee=booklet.annee,
    )


@transaction.atomic
def record_antidated_entry(
    *,
    member: Member,
    product: str,
    sens: str,
    montant: Decimal,
    date_op,
    booklet_order: BookletOrder | None = None,
    cycle_id=None,
    note: str = "",
    recorded_by=None,
) -> AntidatedResult:
    """Enregistre UNE écriture antidatée. Voir le docstring du module.

    Args:
        product : ``"collecte"``, ``"classique"``, ``"tontine"`` ou
                  ``"caisse_scolaire"``.
        sens    : ``"depot"`` ou ``"retrait"``.
        montant : > 0.
        date_op : date/datetime dans le passé (pas dans le futur).
        booklet_order : carnet explicite ; sinon résolu à la date de l'écriture
                        (typé selon le produit).
        cycle_id : OBLIGATOIRE pour tontine/caisse — la collecte visée.

    Lève ``AntidatedEntryError`` sur toute incohérence. Un retrait antidaté PEUT
    rendre le solde négatif : c'est une reprise d'historique papier, on saisit
    les écritures dans l'ordre réel (un retrait peut précéder les dépôts qui le
    couvrent, ou reconstituer un découvert historique). Le contrôle de solde ne
    s'applique QUE sur les retraits en direct (``request_withdrawal``).
    """
    _all_products = (
        PRODUCT_COLLECTE, PRODUCT_CLASSIQUE, PRODUCT_TONTINE, PRODUCT_CAISSE,
    )
    if product not in _all_products:
        raise AntidatedEntryError(f"Produit inconnu : {product!r}.")
    if sens not in (SENS_DEPOT, SENS_RETRAIT):
        raise AntidatedEntryError(f"Sens inconnu : {sens!r}.")

    montant = Decimal(montant)
    if montant <= 0:
        raise AntidatedEntryError("Le montant doit être strictement positif.")

    date_dt = _as_aware(date_op)
    # Une écriture antidatée est, par définition, dans le passé. On tolère
    # aujourd'hui mais on refuse le futur (ce serait une saisie normale).
    today = timezone.localdate()
    op_day = date_dt.date() if isinstance(date_dt, datetime) else date_dt
    if op_day > today:
        raise AntidatedEntryError(
            "Une écriture antidatée ne peut pas être dans le futur."
        )

    # Collectes particulières : chemin dédié (solde par participation/cycle).
    if product in _SPECIAL_PRODUCTS:
        return _record_antidated_special(
            member=member,
            product=product,
            sens=sens,
            montant=montant,
            date_dt=date_dt,
            op_day=op_day,
            cycle_id=cycle_id,
            note=note,
            recorded_by=recorded_by,
        )

    if booklet_order is not None and booklet_order.member_id != member.id:
        raise AntidatedEntryError(
            "Le carnet indiqué n'appartient pas à ce membre."
        )
    booklet = booklet_order or BookletOrder.for_member_at(member, op_day)

    signed = montant if sens == SENS_DEPOT else -montant

    if product == PRODUCT_COLLECTE:
        # date_ouverture est NOT NULL : on la fournit au cas où le membre n'a
        # pas encore de compte collecte (reprise d'historique d'un ancien
        # carnet). On l'ancre à la date de l'écriture, cohérent avec le passé
        # qu'on reconstitue.
        SavingsAccount.objects.get_or_create(
            member=member, defaults={"date_ouverture": op_day}
        )
        account = SavingsAccount.objects.select_for_update().get(member=member)
        # Reprise d'historique : le solde peut passer négatif (retrait saisi
        # avant ses dépôts, ou découvert historique reconstitué). Pas de
        # garde-fou ici — cf. docstring.
        nouveau_solde = Decimal(account.solde) + signed
        account.solde = nouveau_solde
        account.save(update_fields=["solde", "updated_at"])
        row = SavingsTransaction.objects.create(
            account=account,
            payment=None,
            type_op=(
                SavingsTransaction.TypeOp.DEPOT
                if sens == SENS_DEPOT
                else SavingsTransaction.TypeOp.RETRAIT
            ),
            montant=montant,
            solde_apres=nouveau_solde,
            date=date_dt,
            booklet_order=booklet,
        )
        entite_type = "SavingsTransaction"
    else:
        ClassicSavingsAccount.objects.get_or_create(
            member=member, defaults={"date_ouverture": op_day}
        )
        account = (
            ClassicSavingsAccount.objects.select_for_update().get(member=member)
        )
        # Reprise d'historique : solde négatif toléré (cf. docstring).
        nouveau_solde = Decimal(account.solde) + signed
        account.solde = nouveau_solde
        account.save(update_fields=["solde", "updated_at"])
        row = ClassicSavingsTransaction.objects.create(
            account=account,
            payment=None,
            type_op=(
                ClassicSavingsTransaction.TypeOp.DEPOT
                if sens == SENS_DEPOT
                else ClassicSavingsTransaction.TypeOp.RETRAIT
            ),
            montant=montant,
            solde_apres=nouveau_solde,
            date=date_dt,
            booklet_order=booklet,
        )
        entite_type = "ClassicSavingsTransaction"

    record_audit(
        action="savings.antidated_entry",
        entite_type=entite_type,
        entite_id=row.id,
        user=recorded_by,
        details={
            "member_id": member.id,
            "product": product,
            "sens": sens,
            "montant": str(montant),
            "date": op_day.isoformat(),
            "solde_apres": str(nouveau_solde),
            "booklet_order_id": booklet.id if booklet else None,
            "note": note.strip()[:500],
        },
    )

    return AntidatedResult(
        transaction_id=row.id,
        product=product,
        sens=sens,
        montant=montant,
        date=date_dt,
        solde_apres=nouveau_solde,
        booklet_order_id=booklet.id if booklet else None,
    )


def _record_antidated_special(
    *, member, product, sens, montant, date_dt, op_day, cycle_id, note, recorded_by
) -> AntidatedResult:
    """Écriture antidatée sur une collecte particulière (tontine / caisse).

    Cible la participation VALIDÉE du membre dans la collecte ``cycle_id`` et
    mute son solde (négatif toléré, reprise d'historique). Impute au carnet
    typé du membre à la date de l'écriture.
    """
    from apps_coop.special_collections.models import (
        SpecialCollectionCycle,
        SpecialCollectionMembership,
        SpecialCollectionTransaction,
    )

    collection_type = _SPECIAL_PRODUCTS[product]
    if not cycle_id:
        raise AntidatedEntryError(
            "La collecte cible (cycle_id) est obligatoire pour une écriture "
            "tontine / caisse scolaire."
        )
    cycle = SpecialCollectionCycle.objects.filter(
        pk=cycle_id, type=collection_type
    ).first()
    if cycle is None:
        raise AntidatedEntryError("Collecte introuvable.")

    membership = (
        SpecialCollectionMembership.objects.select_for_update()
        .filter(member=member, cycle=cycle)
        .first()
    )
    if membership is None:
        raise AntidatedEntryError(
            "Ce membre ne participe pas à cette collecte."
        )

    # Carnet typé du membre actif à la date de l'écriture (imputation, toléré null).
    carnet_type = {
        PRODUCT_TONTINE: BookletOrder.Type.TONTINE,
        PRODUCT_CAISSE: BookletOrder.Type.CAISSE_SCOLAIRE,
    }[product]
    booklet = BookletOrder.for_member_at(member, op_day, carnet_type)

    signed = montant if sens == SENS_DEPOT else -montant
    nouveau_solde = Decimal(membership.solde) + signed
    membership.solde = nouveau_solde
    membership.save(update_fields=["solde", "updated_at"])

    row = SpecialCollectionTransaction.objects.create(
        membership=membership,
        payment=None,
        booklet_order=booklet,
        type_op=SpecialCollectionTransaction.TypeOp.MANUEL,
        montant=montant,
        solde_apres=nouveau_solde,
        date=date_dt,
        libelle="Reprise historique" + (f" — {note.strip()[:80]}" if note else ""),
    )

    record_audit(
        action="savings.antidated_entry",
        entite_type="SpecialCollectionTransaction",
        entite_id=row.id,
        user=recorded_by,
        details={
            "member_id": member.id,
            "product": product,
            "sens": sens,
            "montant": str(montant),
            "date": op_day.isoformat(),
            "cycle_id": cycle.id,
            "solde_apres": str(nouveau_solde),
            "booklet_order_id": booklet.id if booklet else None,
            "note": note.strip()[:500],
        },
    )

    return AntidatedResult(
        transaction_id=row.id,
        product=product,
        sens=sens,
        montant=montant,
        date=date_dt,
        solde_apres=nouveau_solde,
        booklet_order_id=booklet.id if booklet else None,
    )
