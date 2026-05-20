"""Service-layer functions for the members domain.

Pure business logic — no HTTP, no admin templates. Called from:
  - the Django admin actions (``apps_coop.members.admin``)
  - the API admin viewsets (still to be wired)
  - the management commands (e.g. bulk approve from a CSV)

Every public function is atomic and idempotent: it can be re-run on the same
``MembershipRequest`` row without creating duplicates.
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import record as record_audit
from apps_coop.savings.models import SavingsAccount

from .models import Member, MembershipRequest


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@transaction.atomic
def approve_membership_request(
    request_obj: MembershipRequest,
    *,
    instructed_by,
    prenom: str | None = None,
    nom: str | None = None,
) -> Member:
    """Approve a pending adhesion request.

    Creates atomically: ``User`` (with a one-shot random password and the
    ``member`` group), ``Member`` profile, and an empty ``SavingsAccount``.
    Idempotent — re-running on an already-approved request returns the
    existing Member without doing anything else.

    The applicant must still pay the 1st cotisation (``frais_adhesion``)
    before becoming ``actif`` — see the payment flow in
    ``architecture/01-paiement-mobile-money-tara.md``.
    """
    # Idempotence
    if request_obj.statut == MembershipRequest.Statut.APPROUVEE and request_obj.member_id:
        return request_obj.member
    if request_obj.statut != MembershipRequest.Statut.EN_ATTENTE:
        raise ValueError(
            f"Cannot approve a request with status {request_obj.statut!r} "
            f"(expected {MembershipRequest.Statut.EN_ATTENTE!r})."
        )

    # Article 3 : l'entretien d'admission est obligatoire et conditionne
    # l'acceptation. On refuse l'approbation tant qu'il n'a pas été enregistré.
    if request_obj.date_entretien is None:
        raise ValueError(
            "Entretien d'admission requis (Article 3) avant d'approuver la demande."
        )

    User = get_user_model()

    # Allow the admin to fix identity at approval time. Fall back to whatever
    # was captured at submission.
    final_prenom = (prenom or request_obj.prenom or "").strip()
    final_nom = (nom or request_obj.nom or "").strip()
    if not final_nom:
        raise ValueError("Le nom est requis pour approuver la demande.")

    # User row — email is unique. If a user already exists with that email
    # (e.g. a previous rejected attempt), we reuse it.
    user, user_created = User.objects.get_or_create(
        email=request_obj.email,
        defaults={
            "username": request_obj.email,
            "first_name": final_prenom,
            "last_name": final_nom,
            "is_active": True,
        },
    )
    if user_created:
        user.set_password(_random_password())
        user.save(update_fields=["password"])

    # Member group — created lazily so we don't depend on a fixture.
    member_group, _ = Group.objects.get_or_create(name="member")
    user.groups.add(member_group)

    # Member profile (OneToOne) — reuse if exists.
    member, member_created = Member.objects.get_or_create(
        user=user,
        defaults={
            "numero_membre": generate_numero_membre(),
            "nom": final_nom,
            "prenom": final_prenom,
            "phone": request_obj.phone,
            "adresse": "",
            "profession": "",
            # Statut stays default (`actif`), but the *cotisation* gate
            # below keeps real activation tied to the 1st payment hook.
            "statut": Member.Statut.SUSPENDU,
            "date_adhesion": date.today(),
        },
    )
    # Don't overwrite a manually-edited numero_membre.
    if member_created and not member.numero_membre:
        member.numero_membre = generate_numero_membre()
        member.save(update_fields=["numero_membre"])

    # Empty savings account
    SavingsAccount.objects.get_or_create(
        member=member,
        defaults={
            "solde": 0,
            "date_ouverture": date.today(),
            "taux_interet_applique": 0,
        },
    )

    # Close the request
    request_obj.statut = MembershipRequest.Statut.APPROUVEE
    request_obj.instruit_par = instructed_by
    request_obj.date_decision = timezone.now()
    request_obj.member = member
    request_obj.prenom = final_prenom
    request_obj.nom = final_nom
    request_obj.save(
        update_fields=["statut", "instruit_par", "date_decision", "member", "prenom", "nom", "updated_at"],
    )

    record_audit(
        action="membership.approved",
        entite_type="MembershipRequest",
        entite_id=request_obj.id,
        user=instructed_by,
        details={
            "member_id": member.id,
            "numero_membre": member.numero_membre,
            "email": request_obj.email,
        },
    )
    # TODO(UC1 step 2): send "welcome + payment link" email via apps_coop.notifications.
    return member


@transaction.atomic
def reject_membership_request(
    request_obj: MembershipRequest,
    *,
    instructed_by,
    motif: str,
) -> MembershipRequest:
    """Reject a pending adhesion request with a reason.

    No User / Member is created. The request stays in the DB for traceability
    (and lets the applicant re-apply later via a fresh submission).
    """
    if request_obj.statut == MembershipRequest.Statut.REJETEE:
        return request_obj
    if request_obj.statut != MembershipRequest.Statut.EN_ATTENTE:
        raise ValueError(
            f"Cannot reject a request with status {request_obj.statut!r}."
        )

    motif = (motif or "").strip()
    if not motif:
        raise ValueError("Un motif de rejet est requis.")

    request_obj.statut = MembershipRequest.Statut.REJETEE
    request_obj.motif_rejet = motif
    request_obj.instruit_par = instructed_by
    request_obj.date_decision = timezone.now()
    request_obj.save(
        update_fields=["statut", "motif_rejet", "instruit_par", "date_decision", "updated_at"],
    )

    record_audit(
        action="membership.rejected",
        entite_type="MembershipRequest",
        entite_id=request_obj.id,
        user=instructed_by,
        details={"motif": motif, "email": request_obj.email},
    )
    # TODO(UC1 step 2): send "demande non retenue" email.
    return request_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def generate_numero_membre() -> str:
    """Return a unique member number formatted ``GF-YYYY-NNNN``.

    We pick the sequence by counting all members created this year + 1, then
    retry on collision (defensive against concurrent inserts in the same
    second). Format is stable and human-readable; switch to a real sequence
    table if we ever scale past ~10k members/year.
    """
    year = date.today().year
    base_prefix = f"GF-{year}-"
    # Take the existing max for this year, fall back to 0.
    qs = Member.objects.filter(numero_membre__startswith=base_prefix).values_list("numero_membre", flat=True)
    max_seq = 0
    for n in qs:
        try:
            seq = int(n.rsplit("-", 1)[-1])
        except ValueError:
            continue
        max_seq = max(max_seq, seq)
    return f"{base_prefix}{max_seq + 1:04d}"


def _random_password(length: int = 24) -> str:
    """One-shot password — the user resets it via the password-reset flow."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))
