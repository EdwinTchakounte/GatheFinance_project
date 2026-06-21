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
import re
import secrets
import string
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps_coop.audit.services import (
    get_str_setting,
    record as record_audit,
)
from apps_coop.savings.models import SavingsAccount

from .models import BRCDocument, Member, MembershipRequest


logger = logging.getLogger(__name__)


@transaction.atomic
def confirm_member_reinscription(
    member: Member,
    *,
    confirmed_by,
    paid_amount=None,
    note: str = "",
) -> Member:
    """A2 — Acte la re-souscription annuelle d'un membre (alerte douce + acte admin).

    Met à jour ``date_derniere_reinscription`` à la date du jour, ce qui
    décale la prochaine échéance de 12 mois. Ne charge **pas** automatiquement
    les frais : l'admin enregistre le paiement séparément via le flow standard
    (les frais 10 000 + 2 000 sont identiques à l'adhésion, on s'appuie sur le
    catalogue ``FeeType`` existant).

    Idempotent : si la dernière réinscription date d'aujourd'hui (cas double-clic),
    on retourne sans rien refaire.
    """
    today = timezone.localdate()
    if member.date_derniere_reinscription == today:
        return member  # déjà confirmé aujourd'hui — idempotent

    previous = member.date_derniere_reinscription
    member.date_derniere_reinscription = today
    member.save(update_fields=["date_derniere_reinscription", "updated_at"])

    record_audit(
        action="member.reinscription_confirmed",
        entite_type="Member",
        entite_id=member.id,
        user=confirmed_by,
        details={
            "previous_anchor": previous.isoformat() if previous else None,
            "new_anchor": today.isoformat(),
            "paid_amount": str(paid_amount) if paid_amount is not None else None,
            "note": note,
        },
    )

    # Notif/email "réinscription confirmée" (event catalogable via EXT-5).
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(
            "member.reinscription_confirmed",
            member=member,
            context={
                "prenom": member.prenom,
                "numero_membre": member.numero_membre,
                "date_confirmation": today.isoformat(),
                "prochaine_echeance": (member.prochaine_reinscription_due or today).isoformat(),
            },
        )
    except Exception:  # noqa: BLE001
        logger.warning("emit_event member.reinscription_confirmed failed", exc_info=True)

    return member


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
    # UC1 step 2 — e-mail de bienvenue + lien de paiement de la 1ʳᵉ cotisation.
    # Différé au commit : on n'envoie l'e-mail QUE si la transaction réussit
    # (évite un mail de bienvenue pour une approbation qui rollback ensuite).
    transaction.on_commit(lambda: _send_welcome_email(member, request_obj.email))
    return member


def _send_welcome_email(member: Member, to_email: str) -> None:
    """E-mail de bienvenue (UC1) — jamais bloquant pour l'approbation.

    Joint l'attestation d'adhésion (PDF) générée à la volée. Si la génération
    du PDF échoue pour une raison quelconque, on envoie quand même l'e-mail
    sans pièce jointe — l'approbation ne doit jamais être pénalisée.
    """
    if not to_email:
        return
    try:
        from decimal import Decimal

        from apps_coop.payments.models import FeeType

        # « Première cotisation » = frais d'adhésion + frais d'inscription
        # (montants exacts du Règlement, lus en base — jamais codés en dur).
        fees = FeeType.objects.filter(
            code__in=[FeeType.Code.ADHESION, FeeType.Code.INSCRIPTION]
        )
        total = sum((f.montant for f in fees), Decimal("0"))
        frais_montant = f"{int(total):,}".replace(",", " ")

        # Attestation d'adhésion (PDF) — jointe si la génération réussit, sinon
        # on n'empêche pas l'envoi de l'e-mail.
        attachments: list[tuple[str, bytes, str]] = []
        try:
            from .attestation import build_attestation_pdf

            pdf_bytes = build_attestation_pdf(member)
            attachments.append(
                ("attestation_adhesion.pdf", pdf_bytes, "application/pdf")
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "attestation PDF generation failed for %s — sending email without it",
                member.numero_membre,
                exc_info=True,
            )

        # Règlement intérieur (CooperativeAsset singleton) — joint si uploadé
        # par l'admin via /api/v1/audit/admin/cooperative-asset/reglement/.
        try:
            from apps_coop.audit.models import CooperativeAsset

            asset = CooperativeAsset.get_solo()
            if asset.reglement_interieur:
                with asset.reglement_interieur.open("rb") as f:
                    regl_bytes = f.read()
                attachments.append(
                    ("reglement_interieur.pdf", regl_bytes, "application/pdf")
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "reglement PDF attach failed for %s — sending email without it",
                member.numero_membre,
                exc_info=True,
            )

        from apps_coop.notifications.events import emit_event

        emit_event(
            "member.welcome",
            member=member,
            to_email=to_email,  # adresse de l'inscription, pas forcément user.email
            context={
                "prenom": member.prenom,
                "nom": member.nom,
                "numero_membre": member.numero_membre,
                "frais_montant": frais_montant,
                "portal_url": getattr(settings, "FRONTEND_PUBLIC_URL", "http://localhost:3200"),
            },
            attachments=attachments or None,
        )
    except Exception:  # noqa: BLE001
        logger.warning("member.welcome email skipped for %s", to_email, exc_info=True)


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
    # Email « demande non retenue » (best-effort — ne bloque jamais le rejet).
    if request_obj.email:
        try:
            from apps_coop.notifications.events import emit_event

            emit_event(
                "member.rejected",
                to_email=request_obj.email,  # pas encore de Member créé
                context={
                    "prenom": request_obj.prenom,
                    "nom": request_obj.nom,
                    "motif": motif,
                    "portal_url": getattr(
                        settings, "FRONTEND_PUBLIC_URL", "http://localhost:3200"
                    ),
                },
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "member.rejected email skipped for %s", request_obj.email, exc_info=True
            )
    return request_obj


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_DEFAULT_ID_FORMAT = "GF-{year}-{seq:04d}"


def generate_numero_membre() -> str:
    """Return a unique ``numero_membre`` (= numéro d'identification §2).

    Format **configurable** via ``AppSetting member.id.format`` (refonte 2026).
    Le placeholder ``{year}`` est obligatoire et ``{seq}`` (avec ou sans
    padding ``{seq:04d}``) est obligatoire. Défaut ``GF-{year}-{seq:04d}``
    → ``GF-2026-0001``, ``GF-2026-0002``, …

    On résout le prochain ``seq`` en regardant le max existant pour le
    préfixe rendu (tout ce qui précède ``{seq``). Format malformé → on
    retombe sur le défaut pour ne jamais bloquer la création de membre.
    """
    raw_fmt = get_str_setting("member.id.format", _DEFAULT_ID_FORMAT)
    fmt = raw_fmt if "{seq" in raw_fmt and "{year}" in raw_fmt else _DEFAULT_ID_FORMAT
    year = date.today().year

    try:
        prefix_template = fmt[: fmt.index("{seq")]
        prefix = prefix_template.format(year=year)
    except (KeyError, ValueError, IndexError):
        prefix = f"GF-{year}-"
        fmt = _DEFAULT_ID_FORMAT

    qs = (
        Member.objects.filter(numero_membre__startswith=prefix)
        .values_list("numero_membre", flat=True)
    )
    max_seq = 0
    for numero in qs:
        rest = numero[len(prefix):]
        match = re.match(r"^(\d+)", rest)
        if match:
            try:
                max_seq = max(max_seq, int(match.group(1)))
            except ValueError:
                continue

    next_seq = max_seq + 1
    try:
        return fmt.format(year=year, seq=next_seq)
    except (KeyError, ValueError, IndexError):
        return _DEFAULT_ID_FORMAT.format(year=year, seq=next_seq)


# ---------------------------------------------------------------------------
# BRC — Broad Range Consulting (LOT 1 refonte 2026)
# ---------------------------------------------------------------------------


@transaction.atomic
def upload_brc_document(
    *,
    member: Member,
    fichier,
    nom_original: str = "",
    taille: int = 0,
) -> BRCDocument:
    """Le membre dépose un justificatif BRC.

    Crée un ``BRCDocument`` en statut ``EN_ATTENTE``. Le membre peut
    re-uploader autant de fois qu'il veut (chaque ligne garde son
    historique). L'admin gère la validation séparément.
    """
    doc = BRCDocument.objects.create(
        member=member,
        fichier=fichier,
        nom_original=nom_original or getattr(fichier, "name", ""),
        taille=taille or getattr(fichier, "size", 0),
        statut=BRCDocument.Statut.EN_ATTENTE,
    )
    record_audit(
        action="member.brc_document_uploaded",
        entite_type="BRCDocument",
        entite_id=doc.id,
        user=member.user,
        details={
            "member_id": member.id,
            "numero_membre": member.numero_membre,
            "nom_original": doc.nom_original,
            "taille": doc.taille,
        },
    )
    _emit_brc_event(
        "member.brc_document_uploaded",
        member=member,
        context={
            "prenom": member.prenom,
            "numero_membre": member.numero_membre,
            "nom_original": doc.nom_original,
        },
    )
    return doc


@transaction.atomic
def validate_brc_document(*, doc: BRCDocument, validated_by) -> BRCDocument:
    """Admin valide un justificatif BRC → ``Member.is_brc_member = True``.

    Idempotent : revalider un doc déjà ``VALIDE`` n'écrase rien. Tenter de
    valider un doc ``REJETE`` lève ``ValueError`` — le membre doit en
    déposer un nouveau.
    """
    if doc.statut == BRCDocument.Statut.VALIDE:
        return doc
    if doc.statut == BRCDocument.Statut.REJETE:
        raise ValueError(
            "Document déjà rejeté ; demander un nouvel upload au membre."
        )

    now = timezone.now()
    doc.statut = BRCDocument.Statut.VALIDE
    doc.validated_by = validated_by
    doc.validated_at = now
    doc.save(
        update_fields=["statut", "validated_by", "validated_at", "updated_at"]
    )

    member = doc.member
    member.is_brc_member = True
    member.brc_validated_at = now
    member.brc_validated_by = validated_by
    member.save(
        update_fields=[
            "is_brc_member",
            "brc_validated_at",
            "brc_validated_by",
            "updated_at",
        ]
    )

    record_audit(
        action="member.brc_validated",
        entite_type="Member",
        entite_id=member.id,
        user=validated_by,
        details={
            "doc_id": doc.id,
            "numero_membre": member.numero_membre,
        },
    )
    _emit_brc_event(
        "member.brc_validated",
        member=member,
        context={
            "prenom": member.prenom,
            "numero_membre": member.numero_membre,
            "date_validation": now.date().isoformat(),
        },
    )
    return doc


@transaction.atomic
def reject_brc_document(
    *,
    doc: BRCDocument,
    rejected_by,
    motif: str,
) -> BRCDocument:
    """Admin rejette un justificatif BRC avec motif obligatoire.

    Ne touche PAS ``Member.is_brc_member`` (le membre peut avoir déjà été
    validé via un autre doc — un rejet d'un doc plus ancien ne révoque pas
    cet état).
    """
    if doc.statut == BRCDocument.Statut.REJETE:
        return doc
    if doc.statut == BRCDocument.Statut.VALIDE:
        raise ValueError("Document déjà validé ; impossible de rejeter.")
    motif_clean = (motif or "").strip()
    if not motif_clean:
        raise ValueError("Un motif de rejet est requis.")

    now = timezone.now()
    doc.statut = BRCDocument.Statut.REJETE
    doc.motif_rejet = motif_clean
    doc.validated_by = rejected_by
    doc.validated_at = now
    doc.save(
        update_fields=[
            "statut",
            "motif_rejet",
            "validated_by",
            "validated_at",
            "updated_at",
        ]
    )

    record_audit(
        action="member.brc_rejected",
        entite_type="BRCDocument",
        entite_id=doc.id,
        user=rejected_by,
        details={
            "motif": motif_clean,
            "member_id": doc.member.id,
            "numero_membre": doc.member.numero_membre,
        },
    )
    _emit_brc_event(
        "member.brc_rejected",
        member=doc.member,
        context={
            "prenom": doc.member.prenom,
            "numero_membre": doc.member.numero_membre,
            "motif": motif_clean,
        },
    )
    return doc


def _emit_brc_event(code: str, *, member: Member, context: dict) -> None:
    """Best-effort event emission — never blocks the BRC workflow."""
    try:
        from apps_coop.notifications.events import emit_event

        emit_event(code, member=member, context=context)
    except Exception:  # noqa: BLE001
        logger.warning("emit_event %s failed", code, exc_info=True)


def _random_password(length: int = 24) -> str:
    """One-shot password — the user resets it via the password-reset flow."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))
