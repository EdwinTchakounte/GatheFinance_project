"""Logique métier des tontines de GROUPE (réunions de quartier) — 2026-08.

La réunion a sa propre cagnotte (``GroupTontine.solde``). Opérations :
  • cotisation      : un membre alimente la cagnotte (MoMo / manuel / transfert) ;
  • versement bénéf : le trésorier/président verse un montant (fixé) à un membre
                      depuis la cagnotte → crédite l'épargne classique du membre ;
  • prêt            : la réunion prête à un membre → crédite son épargne, suivi
                      d'un ``GroupTontineLoan`` (solde restant) ;
  • remboursement   : le membre rembourse → la cagnotte est recréditée.

Rôles : le président assigne le trésorier ; président/trésorier peuvent verser,
prêter, clôturer un tour. Toutes les mutations passent par ``select_for_update``
et écrivent un ledger append-only.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.members.models import BookletOrder

from .models import (
    GroupTontine,
    GroupTontineLoan,
    GroupTontineMember,
    GroupTontineTransaction,
)


class GroupTontineError(Exception):
    """Erreur métier tontine de groupe (droit, solde, membre hors groupe…)."""


# ── Rôles / droits ───────────────────────────────────────────────────────────
def role_of(group: GroupTontine, member) -> str | None:
    """Rôle du membre dans la réunion, ou ``None`` s'il n'en fait pas partie."""
    row = GroupTontineMember.objects.filter(
        group=group, member=member, actif=True
    ).first()
    return row.role if row else None


def member_permissions(group: GroupTontine, member) -> dict:
    """Actions habilitées pour ``member`` dans la réunion (dict de booléens).

    Résolution :
      * président → TOUTES les actions (autorité pleine, non retirable) ;
      * trésorier (intégré) → gère les fonds (payout + prêt) + cotisations ;
      * membre (intégré) → aucune action de gestion ;
      * + un éventuel rôle personnalisé CUMULE ses actions par-dessus.
    """
    from .models import GroupTontineRole

    fields = GroupTontineRole.ACTION_FIELDS
    perms = {f: False for f in fields}
    row = (
        GroupTontineMember.objects.filter(group=group, member=member, actif=True)
        .select_related("custom_role")
        .first()
    )
    if row is None:
        return perms
    if row.role == GroupTontineMember.Role.PRESIDENT:
        return {f: True for f in fields}
    if row.role == GroupTontineMember.Role.TRESORIER:
        perms["can_manage_funds"] = True
        perms["can_grant_loan"] = True
        perms["can_record_cotisation"] = True
    if row.custom_role is not None:
        for f in fields:
            perms[f] = perms[f] or bool(getattr(row.custom_role, f))
    return perms


def _has_perm(group: GroupTontine, member, perm: str) -> bool:
    return member_permissions(group, member).get(perm, False)


def _can_manage_funds(group: GroupTontine, member) -> bool:
    """Rétro-compat : « peut gérer les fonds » (payout / remboursement)."""
    return _has_perm(group, member, "can_manage_funds")


# ── Acteur / notifications (traçabilité affichée aux membres) ────────────────
def _as_user(by):
    """Normalise ``by`` (User OU Member) en User, ou None."""
    if by is None:
        return None
    if hasattr(by, "member") or getattr(by, "is_authenticated", False):
        return by  # déjà un User
    return getattr(by, "user", None)


def actor_name(user) -> str:
    """Nom lisible d'un acteur (pour l'historique / la notif)."""
    if user is None:
        return "la coopérative"
    m = getattr(user, "member", None)
    if m is not None and (m.prenom or m.nom):
        return f"{m.prenom} {m.nom}".strip()
    full = f"{user.first_name} {user.last_name}".strip()
    return full or "la coopérative"


def _notify(user, *, type, message):
    if user is None:
        return
    try:
        from apps_coop.notifications.services import create_notification

        create_notification(user=user, type=type, message=message, lien="/notifications")
    except Exception:  # noqa: BLE001 — une notif ne casse jamais le flux métier
        pass


# ── Création / roster / rôles (admin, ou président pour certains) ─────────────
def create_group(
    *, nom, description="", montant_cotisation=None, roster=None, by=None
) -> GroupTontine:
    """Crée une réunion et son roster.

    ``roster`` : liste de dicts ``{"member": Member, "role": <role>}``. Un
    unique président et un unique trésorier sont attendus (les autres = membre).
    """
    group = GroupTontine.objects.create(
        nom=nom.strip(),
        description=(description or "").strip(),
        montant_cotisation=montant_cotisation or Decimal("0"),
        created_by=by,
    )
    for entry in roster or []:
        GroupTontineMember.objects.create(
            group=group,
            member=entry["member"],
            role=entry.get("role", GroupTontineMember.Role.MEMBRE),
        )
    record_audit(
        action="group_tontine.created",
        entite_type="GroupTontine",
        entite_id=group.id,
        user=by,
        details={"nom": group.nom, "roster": len(roster or [])},
    )
    return group


def add_member(group, member, role=GroupTontineMember.Role.MEMBRE, *, by=None):
    row, created = GroupTontineMember.objects.get_or_create(
        group=group, member=member, defaults={"role": role}
    )
    if not created and not row.actif:
        row.actif = True
        row.role = role
        row.save(update_fields=["actif", "role", "updated_at"])
    record_audit(
        action="group_tontine.member_added",
        entite_type="GroupTontineMember",
        entite_id=row.id,
        user=by,
        details={"group_id": group.id, "member_id": member.id, "role": role},
    )
    return row


def remove_member(group, member, *, by=None):
    row = GroupTontineMember.objects.filter(group=group, member=member).first()
    if row is None:
        return
    row.actif = False
    row.save(update_fields=["actif", "updated_at"])
    record_audit(
        action="group_tontine.member_removed",
        entite_type="GroupTontineMember",
        entite_id=row.id,
        user=by,
        details={"group_id": group.id, "member_id": member.id},
    )


def set_role(group, member, role, *, by=None):
    """Change le rôle d'un membre. (La vérification de droit — président/admin —
    est faite dans la vue.)"""
    if role not in GroupTontineMember.Role.values:
        raise GroupTontineError("Rôle inconnu.")
    row = GroupTontineMember.objects.filter(
        group=group, member=member, actif=True
    ).first()
    if row is None:
        raise GroupTontineError("Ce membre ne fait pas partie de la réunion.")
    # Garde-fou : ne pas laisser la réunion sans président (revote = promouvoir
    # le nouveau président AVANT de rétrograder l'ancien).
    if (
        row.role == GroupTontineMember.Role.PRESIDENT
        and role != GroupTontineMember.Role.PRESIDENT
        and not GroupTontineMember.objects.filter(
            group=group, role=GroupTontineMember.Role.PRESIDENT, actif=True
        ).exclude(pk=row.pk).exists()
    ):
        raise GroupTontineError(
            "Désigne d'abord un nouveau président avant de retirer ce rôle."
        )
    row.role = role
    row.save(update_fields=["role", "updated_at"])
    record_audit(
        action="group_tontine.role_set",
        entite_type="GroupTontineMember",
        entite_id=row.id,
        user=by,
        details={"group_id": group.id, "member_id": member.id, "role": role},
    )
    return row


# ── Rôles personnalisés (actions rattachées, propres à la réunion) ────────────
def _clean_role_perms(permissions) -> dict:
    """Ne retient que les actions du catalogue (ignore les clés inconnues)."""
    from .models import GroupTontineRole

    permissions = permissions or {}
    return {f: bool(permissions.get(f, False)) for f in GroupTontineRole.ACTION_FIELDS}


def create_custom_role(group, nom, permissions=None, *, by=None):
    """Crée un rôle personnalisé (nom + actions cochées) pour la réunion."""
    from .models import GroupTontineRole

    nom = (nom or "").strip()
    if not nom:
        raise GroupTontineError("Le nom du rôle est obligatoire.")
    if GroupTontineRole.objects.filter(group=group, nom__iexact=nom).exists():
        raise GroupTontineError("Un rôle porte déjà ce nom dans la réunion.")
    role = GroupTontineRole.objects.create(
        group=group, nom=nom, **_clean_role_perms(permissions)
    )
    record_audit(
        action="group_tontine.custom_role_created",
        entite_type="GroupTontineRole",
        entite_id=role.id,
        user=_as_user(by),
        details={"group_id": group.id, "nom": nom, **role.as_permissions()},
    )
    return role


def update_custom_role(role, *, nom=None, permissions=None, by=None):
    """Renomme et/ou met à jour les actions d'un rôle personnalisé."""
    from .models import GroupTontineRole

    fields = []
    if nom is not None:
        nom = nom.strip()
        if not nom:
            raise GroupTontineError("Le nom du rôle est obligatoire.")
        clash = (
            GroupTontineRole.objects.filter(group=role.group, nom__iexact=nom)
            .exclude(pk=role.pk)
            .exists()
        )
        if clash:
            raise GroupTontineError("Un rôle porte déjà ce nom dans la réunion.")
        role.nom = nom
        fields.append("nom")
    if permissions is not None:
        for f, v in _clean_role_perms(permissions).items():
            setattr(role, f, v)
        fields.extend(GroupTontineRole.ACTION_FIELDS)
    if fields:
        role.save(update_fields=[*fields, "updated_at"])
    record_audit(
        action="group_tontine.custom_role_updated",
        entite_type="GroupTontineRole",
        entite_id=role.id,
        user=_as_user(by),
        details={"group_id": role.group_id, "nom": role.nom, **role.as_permissions()},
    )
    return role


def delete_custom_role(role, *, by=None):
    """Supprime un rôle personnalisé (les membres qui le portaient le perdent —
    ``custom_role`` repasse à NULL via SET_NULL)."""
    rid, gid, nom = role.id, role.group_id, role.nom
    role.delete()
    record_audit(
        action="group_tontine.custom_role_deleted",
        entite_type="GroupTontineRole",
        entite_id=rid,
        user=_as_user(by),
        details={"group_id": gid, "nom": nom},
    )


def assign_custom_role(group, member, custom_role, *, by=None):
    """Attribue (ou retire si ``custom_role`` est None) un rôle personnalisé à un
    membre de la réunion."""
    row = GroupTontineMember.objects.filter(
        group=group, member=member, actif=True
    ).first()
    if row is None:
        raise GroupTontineError("Ce membre ne fait pas partie de la réunion.")
    if custom_role is not None and custom_role.group_id != group.id:
        raise GroupTontineError("Ce rôle n'appartient pas à cette réunion.")
    row.custom_role = custom_role
    row.save(update_fields=["custom_role", "updated_at"])
    record_audit(
        action="group_tontine.custom_role_assigned",
        entite_type="GroupTontineMember",
        entite_id=row.id,
        user=_as_user(by),
        details={
            "group_id": group.id,
            "member_id": member.id,
            "custom_role_id": custom_role.id if custom_role else None,
        },
    )
    return row


# ── Crédit du compte épargne classique d'un membre (bénéficiaire / emprunteur)
def _credit_member_classic(member, montant, *, libelle):
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    ClassicSavingsAccount.objects.get_or_create(
        member=member, defaults={"date_ouverture": timezone.localdate()}
    )
    account = (
        ClassicSavingsAccount.objects.select_for_update().get(member=member)
    )
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


# ── Cotisation (entrée dans la cagnotte) ─────────────────────────────────────
def credit_cotisation(payment) -> GroupTontineTransaction:
    """Crédite la cagnotte suite à un versement validé (hook paiement).

    Si le versement cible un PRÊT (``payment.group_loan``), il le rembourse au
    lieu d'alimenter la cagnotte comme cotisation — l'argent est réel (MoMo), on
    ne débite donc pas l'épargne (``payment`` fourni)."""
    if payment.group_loan_id is not None:
        return repay_loan(
            loan=payment.group_loan, montant=payment.montant, payment=payment
        )
    group = payment.group_tontine
    if group is None:
        raise GroupTontineError("Cotisation sans réunion cible.")
    return _apply_cotisation(
        group=group, member=payment.member, montant=payment.montant,
        payment=payment, is_manual=payment.source == payment.Source.MANUEL,
        acted_by=getattr(payment.member, "user", None),
    )


def _apply_cotisation(*, group, member, montant, payment=None, is_manual=False,
                      acted_by=None):
    with db_transaction.atomic():
        grp = GroupTontine.objects.select_for_update().get(pk=group.pk)
        if not grp.is_open:
            raise GroupTontineError("Cette réunion est clôturée.")
        if role_of(grp, member) is None:
            raise GroupTontineError("Ce membre ne fait pas partie de la réunion.")
        grp.solde = Decimal(grp.solde) + Decimal(montant)
        grp.save(update_fields=["solde", "updated_at"])
        row = GroupTontineTransaction.objects.create(
            group=grp,
            member=member,
            payment=payment,
            acted_by=acted_by,
            type_op=GroupTontineTransaction.TypeOp.COTISATION,
            montant=montant,
            solde_apres=grp.solde,
            date=payment.date_versement if payment else timezone.now(),
            libelle="Cotisation agence" if is_manual else "Cotisation",
        )
    record_audit(
        action="group_tontine.cotisation",
        entite_type="GroupTontineTransaction",
        entite_id=row.id,
        details={"group_id": grp.id, "member_id": member.id, "montant": str(montant)},
    )
    # Notifie le cotisant (débit/versement + crédit à la collecte).
    _notify(
        getattr(member, "user", None),
        type="collecte.cotisation",
        message=(
            f"Cotisation de {int(Decimal(montant))} FCFA à « {grp.nom} » "
            f"enregistrée (cagnotte : {int(grp.solde)} FCFA)."
        ),
    )
    return row


def transfer_cotisation(*, group, member, montant):
    """Cotisation par prélèvement sur l'épargne classique disponible du membre.

    Débit épargne ET crédit cagnotte dans UNE SEULE transaction (atomique) : un
    échec après le débit ne peut pas laisser l'argent « perdu ».
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    montant = Decimal(montant)
    if montant <= 0:
        raise GroupTontineError("Montant invalide.")
    with db_transaction.atomic():
        grp = GroupTontine.objects.select_for_update().get(pk=group.pk)
        if not grp.is_open:
            raise GroupTontineError("Cette réunion est clôturée.")
        if role_of(grp, member) is None:
            raise GroupTontineError("Ce membre ne fait pas partie de la réunion.")

        account = (
            ClassicSavingsAccount.objects.select_for_update()
            .filter(member=member)
            .first()
        )
        dispo = Decimal(account.solde_libre) if account else Decimal("0")
        if account is None or dispo < montant:
            raise GroupTontineError("Épargne classique disponible insuffisante.")
        account.solde = Decimal(account.solde) - montant
        account.save(update_fields=["solde", "updated_at"])
        ClassicSavingsTransaction.objects.create(
            account=account,
            type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
            montant=montant,
            solde_apres=account.solde,
            date=timezone.now(),
            booklet_order=BookletOrder.latest_for(account.member),
        )
        # Crédit de la cagnotte dans la MÊME transaction.
        grp.solde = Decimal(grp.solde) + montant
        grp.save(update_fields=["solde", "updated_at"])
        row = GroupTontineTransaction.objects.create(
            group=grp,
            member=member,
            acted_by=getattr(member, "user", None),
            type_op=GroupTontineTransaction.TypeOp.COTISATION,
            montant=montant,
            solde_apres=grp.solde,
            date=timezone.now(),
            libelle="Cotisation (épargne classique)",
        )
        solde_epargne = Decimal(account.solde)
    record_audit(
        action="group_tontine.cotisation",
        entite_type="GroupTontineTransaction",
        entite_id=row.id,
        details={"group_id": grp.id, "member_id": member.id, "montant": str(montant)},
    )
    # Notifie le membre : débit épargne libre → crédit collecte.
    _notify(
        getattr(member, "user", None),
        type="collecte.cotisation",
        message=(
            f"{int(montant)} FCFA débités de ton épargne libre "
            f"(solde : {int(solde_epargne)} FCFA) et versés à la cotisation "
            f"« {grp.nom} »."
        ),
    )
    return row


# ── Versement à un bénéficiaire (sortie de cagnotte) ─────────────────────────
def payout_beneficiary(*, group, beneficiary, montant, by):
    """Verse ``montant`` de la cagnotte au compte épargne du bénéficiaire.

    Droit : président ou trésorier. Le bénéficiaire doit être membre du groupe.
    Le montant est libre (fixé par le président/trésorier), plafonné au solde.
    """
    montant = Decimal(montant)
    if montant <= 0:
        raise GroupTontineError("Montant invalide.")
    if not _can_manage_funds(group, by):
        raise GroupTontineError(
            "Vous n'avez pas l'autorisation de verser au bénéficiaire dans cette "
            "réunion."
        )
    if role_of(group, beneficiary) is None:
        raise GroupTontineError("Le bénéficiaire doit être membre de la réunion.")

    with db_transaction.atomic():
        grp = GroupTontine.objects.select_for_update().get(pk=group.pk)
        if not grp.is_open:
            raise GroupTontineError("Cette réunion est clôturée.")
        if Decimal(grp.solde) < montant:
            raise GroupTontineError(
                f"Cagnotte insuffisante ({int(grp.solde)} XAF disponibles)."
            )
        grp.solde = Decimal(grp.solde) - montant
        grp.save(update_fields=["solde", "updated_at"])
        _credit_member_classic(
            beneficiary, montant, libelle="Versement tontine de groupe"
        )
        row = GroupTontineTransaction.objects.create(
            group=grp,
            member=beneficiary,
            acted_by=_as_user(by),
            type_op=GroupTontineTransaction.TypeOp.VERSEMENT_BENEFICIAIRE,
            montant=montant,
            solde_apres=grp.solde,
            date=timezone.now(),
            libelle=f"Versement au bénéficiaire (par {actor_name(_as_user(by))})",
        )
    # Notifie le bénéficiaire : reçu X, versé par [acteur].
    _notify(
        getattr(beneficiary, "user", None),
        type="collecte.beneficiaire",
        message=(
            f"Tu as reçu {int(montant)} FCFA de « {grp.nom} » sur ton épargne "
            f"libre, versé par {actor_name(_as_user(by))}."
        ),
    )
    record_audit(
        action="group_tontine.payout",
        entite_type="GroupTontineTransaction",
        entite_id=row.id,
        user=getattr(by, "user", by),
        details={
            "group_id": grp.id, "beneficiary_id": beneficiary.id,
            "montant": str(montant),
        },
    )
    return row


# ── Prêt à un membre (sortie) + remboursement (entrée) ───────────────────────
def grant_loan(*, group, member, montant, by, avaliste=None, avaliste_nom=""):
    """Accorde un prêt de la cagnotte à un membre.

    ``avaliste`` / ``avaliste_nom`` : INFORMATIF uniquement — « à qui se
    rapporter » (pas de gel, pas de garantie, aucun impact financier ; sans
    rapport avec l'avaliste crédit coopérative). ``avaliste`` = un Member (idéal
    si dans le roster), sinon ``avaliste_nom`` = un nom libre.
    """
    montant = Decimal(montant)
    if montant <= 0:
        raise GroupTontineError("Montant invalide.")
    if not _has_perm(group, by, "can_grant_loan"):
        raise GroupTontineError(
            "Vous n'avez pas l'autorisation d'accorder un prêt dans cette réunion."
        )
    if role_of(group, member) is None:
        raise GroupTontineError("L'emprunteur doit être membre de la réunion.")

    with db_transaction.atomic():
        grp = GroupTontine.objects.select_for_update().get(pk=group.pk)
        if not grp.is_open:
            raise GroupTontineError("Cette réunion est clôturée.")
        if Decimal(grp.solde) < montant:
            raise GroupTontineError(
                f"Cagnotte insuffisante ({int(grp.solde)} XAF disponibles)."
            )
        grp.solde = Decimal(grp.solde) - montant
        grp.save(update_fields=["solde", "updated_at"])
        loan = GroupTontineLoan.objects.create(
            group=grp,
            member=member,
            montant=montant,
            solde_restant=montant,
            avaliste=avaliste,
            avaliste_nom=(avaliste_nom or "").strip(),
            created_by=getattr(by, "user", None),
        )
        _credit_member_classic(member, montant, libelle="Prêt tontine de groupe")
        row = GroupTontineTransaction.objects.create(
            group=grp,
            member=member,
            loan=loan,
            acted_by=_as_user(by),
            type_op=GroupTontineTransaction.TypeOp.PRET,
            montant=montant,
            solde_apres=grp.solde,
            date=timezone.now(),
            libelle=f"Prêt à un membre (par {actor_name(_as_user(by))})",
        )
    record_audit(
        action="group_tontine.loan_granted",
        entite_type="GroupTontineLoan",
        entite_id=loan.id,
        user=getattr(by, "user", by),
        details={"group_id": grp.id, "member_id": member.id, "montant": str(montant)},
    )
    return loan, row


def repay_loan(*, loan, montant, by=None, payment=None):
    """Remboursement d'un prêt de réunion — ADOSSÉ à de l'argent réel.

    Le crédit de la cagnotte est couvert soit par un ``payment`` réel (MoMo /
    cash-in : l'argent est déjà entré), soit — à défaut — par un DÉBIT de
    l'épargne classique de l'emprunteur (transfert interne). Jamais de crédit
    « à partir de rien ». Droit : l'emprunteur lui-même, le président ou le
    trésorier.
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
    )

    montant = Decimal(montant)
    if montant <= 0:
        raise GroupTontineError("Montant invalide.")
    with db_transaction.atomic():
        ln = GroupTontineLoan.objects.select_for_update().get(pk=loan.pk)
        if ln.statut == GroupTontineLoan.Statut.SOLDE:
            raise GroupTontineError("Ce prêt est déjà soldé.")
        # Droit : emprunteur, président ou trésorier de la réunion.
        if (
            by is not None
            and getattr(by, "id", None) != ln.member_id
            and not _can_manage_funds(ln.group, by)
        ):
            raise GroupTontineError(
                "Seuls l'emprunteur, le président ou le trésorier peuvent "
                "enregistrer un remboursement."
            )
        applique = min(montant, Decimal(ln.solde_restant))

        # Adossement : sans paiement réel, on débite l'épargne de l'emprunteur.
        if payment is None:
            account = (
                ClassicSavingsAccount.objects.select_for_update()
                .filter(member=ln.member)
                .first()
            )
            dispo = Decimal(account.solde_libre) if account else Decimal("0")
            if account is None or dispo < applique:
                raise GroupTontineError(
                    "Épargne classique disponible insuffisante pour rembourser."
                )
            account.solde = Decimal(account.solde) - applique
            account.save(update_fields=["solde", "updated_at"])
            ClassicSavingsTransaction.objects.create(
                account=account,
                type_op=ClassicSavingsTransaction.TypeOp.RETRAIT,
                montant=applique,
                solde_apres=account.solde,
                date=timezone.now(),
                booklet_order=BookletOrder.latest_for(account.member),
            )

        ln.solde_restant = Decimal(ln.solde_restant) - applique
        if ln.solde_restant <= 0:
            ln.statut = GroupTontineLoan.Statut.SOLDE
        ln.save(update_fields=["solde_restant", "statut", "updated_at"])

        grp = GroupTontine.objects.select_for_update().get(pk=ln.group_id)
        grp.solde = Decimal(grp.solde) + applique
        grp.save(update_fields=["solde", "updated_at"])
        row = GroupTontineTransaction.objects.create(
            group=grp,
            member=ln.member,
            loan=ln,
            payment=payment,
            acted_by=_as_user(by),
            type_op=GroupTontineTransaction.TypeOp.REMBOURSEMENT_PRET,
            montant=applique,
            solde_apres=grp.solde,
            date=payment.date_versement if payment else timezone.now(),
            libelle="Remboursement de prêt",
        )
    record_audit(
        action="group_tontine.loan_repaid",
        entite_type="GroupTontineTransaction",
        entite_id=row.id,
        details={"loan_id": ln.id, "montant": str(applique), "statut": ln.statut},
    )
    return row


# ── Clôture ──────────────────────────────────────────────────────────────────
def close_group(group, *, by):
    if not group.is_open:
        return group
    group.statut = GroupTontine.Statut.CLOS
    group.closed_at = timezone.now()
    group.closed_by = getattr(by, "user", None) or (
        by if not hasattr(by, "member") else None
    )
    group.save(update_fields=["statut", "closed_at", "closed_by", "updated_at"])
    record_audit(
        action="group_tontine.closed",
        entite_type="GroupTontine",
        entite_id=group.id,
        details={"nom": group.nom},
    )
    return group


# ── Visibilité membre ─────────────────────────────────────────────────────────
def groups_for_member(member):
    """Réunions dont ``member`` fait partie (roster actif)."""
    return GroupTontine.objects.filter(
        members__member=member, members__actif=True
    ).distinct().order_by("-created_at")
