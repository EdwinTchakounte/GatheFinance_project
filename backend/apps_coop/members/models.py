"""Members domain — cooperative membres, adhesion requests, attached documents.

We deliberately keep `django.contrib.auth.User` as the auth model and link
`Member` 1-to-1 to it for membres only. Staff (admin / comité) live on
`User` directly via Django Groups, with no `Member` row — this avoids polluting
the member ledger with internal users.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel


class Member(TimestampedModel):
    """Membre — one row per active or historical cooperative member."""

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        SUSPENDU = "suspendu", "Suspendu"
        RADIE = "radie", "Radié"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="member",
    )
    numero_membre = models.CharField(max_length=24, unique=True, db_index=True)
    nom = models.CharField(max_length=120)
    prenom = models.CharField(max_length=120)
    phone = models.CharField(max_length=32, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    profession = models.CharField(max_length=120, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.ACTIF, db_index=True)
    date_adhesion = models.DateField()

    class Meta:
        ordering = ["-date_adhesion"]
        indexes = [models.Index(fields=["statut", "-date_adhesion"])]

    def __str__(self) -> str:
        return f"{self.numero_membre} · {self.prenom} {self.nom}"


class MembershipRequest(TimestampedModel):
    """Public adhesion form submission, instructed by an admin.

    Created by the public ``POST /api/forms/adhesion/`` endpoint (anonymous,
    captcha-protected, rate-limited). Decision is taken from the Django admin
    by an internal user with the ``coop_admin`` group permission, which
    triggers ``services.approve_membership_request`` to create the User +
    Member + SavingsAccount atomically.

    Les champs collectés sont alignés sur l'Article 2 du Règlement Intérieur.
    Les **pièces** (CNI, plan de localisation) sont remises à l'entretien
    physique (Article 3) et téléversées par l'admin via ``Document``.
    """

    class StatutPro(models.TextChoices):
        SALARIE = "salarie", "Salarié"
        COMMERCANT = "commercant", "Commerçant"
        ARTISAN = "artisan", "Artisan"
        SANS_EMPLOI = "sans_emploi", "Sans emploi"
        AUTRE = "autre", "Autre"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"

    # Identity — public form only collects a single `nom` field; `prenom` is
    # filled by the admin during instruction (or left blank).
    nom = models.CharField(max_length=200)
    prenom = models.CharField(max_length=120, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=32, blank=True)
    whatsapp = models.CharField(
        max_length=32,
        blank=True,
        help_text="Numéro WhatsApp — peut être identique au téléphone normal (Article 2).",
    )
    city = models.CharField(max_length=160, blank=True)
    quartier_localite = models.CharField(
        max_length=200,
        blank=True,
        help_text="Lieu précis d'habitation dans la ville (quartier, rue, repère).",
    )
    statut_pro = models.CharField(
        max_length=16,
        choices=StatutPro.choices,
        blank=True,
        default="",
        help_text="Statut social et professionnel (Article 2).",
    )
    # Contact d'urgence — 3 champs (Article 2)
    urgence_nom = models.CharField(max_length=200, blank=True)
    urgence_lien = models.CharField(
        max_length=80,
        blank=True,
        help_text="Lien avec le contact d'urgence (parent, conjoint, ami, …).",
    )
    urgence_phone = models.CharField(max_length=32, blank=True)

    motivation = models.TextField(blank=True, help_text="Free-form 'Pourquoi rejoindre ?' field from the public form.")
    language = models.CharField(max_length=8, default="fr")

    # Traceability — for abuse review / forensic.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)

    # Entretien d'admission (Article 3) — obligatoire et conditionne l'acceptation.
    date_entretien = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de l'entretien avec le comité (Article 3).",
    )
    entretien_avis = models.TextField(
        blank=True,
        help_text="Avis/recommandation du comité après l'entretien.",
    )
    entretien_favorable = models.BooleanField(
        null=True,
        blank=True,
        help_text="True si l'entretien est favorable à l'admission.",
    )

    # Workflow
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)
    motif_rejet = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True, help_text="Private notes for staff — never shown to the applicant.")

    instruit_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="membership_requests_instructed",
    )
    date_decision = models.DateTimeField(null=True, blank=True)

    member = models.OneToOneField(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adhesion_request",
        help_text="Set once the request is approved and a Member is created.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande d'adhésion"
        verbose_name_plural = "Demandes d'adhésion"

    def __str__(self) -> str:
        return f"{self.prenom} {self.nom} ({self.statut})".strip()

    @property
    def display_name(self) -> str:
        return f"{self.prenom} {self.nom}".strip() or self.email


class BookletOrder(TimestampedModel):
    """Commande de carnet d'épargne par un membre.

    Créée automatiquement quand un paiement `frais_carnet` est validé via le
    hook `_hook_carnet_fees`. L'agence imprime ensuite le carnet et passe le
    statut à `en_impression` puis `delivree` depuis le Django admin.

    Workflow :
        payee → en_impression → delivree
    """

    class Statut(models.TextChoices):
        PAYEE = "payee", "Payée"
        EN_IMPRESSION = "en_impression", "En impression"
        DELIVREE = "delivree", "Délivrée"

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="booklet_orders",
    )
    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="booklet_order",
        help_text="Le Payment frais_carnet ayant déclenché la commande.",
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.PAYEE,
        db_index=True,
    )
    date_impression = models.DateTimeField(null=True, blank=True)
    date_delivrance = models.DateTimeField(null=True, blank=True)
    notes_agence = models.TextField(blank=True, help_text="Notes internes (lieu d'impression, retrait…).")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Commande de carnet"
        verbose_name_plural = "Commandes de carnet"

    def __str__(self) -> str:
        return f"Carnet {self.member.numero_membre} · {self.statut}"


class Document(TimestampedModel):
    """Polymorphic file attachment for any business entity (member, loan, request)."""

    class TypeDoc(models.TextChoices):
        PIECE_IDENTITE = "piece_identite", "Pièce d'identité"
        JUSTIFICATIF_REVENU = "justificatif_revenu", "Justificatif de revenu"
        CONTRAT_CREDIT = "contrat_credit", "Contrat de crédit"
        ACTE_GARANTIE = "acte_garantie", "Acte de garantie"
        AUTRE = "autre", "Autre"

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
        help_text="Owning member; nullable when attached to a pre-member request.",
    )
    type_doc = models.CharField(max_length=24, choices=TypeDoc.choices)
    entite_liee_type = models.CharField(
        max_length=32,
        blank=True,
        help_text="Member|Loan|LoanRequest|MembershipRequest",
    )
    entite_liee_id = models.PositiveBigIntegerField(null=True, blank=True)

    fichier = models.FileField(upload_to="coop/documents/%Y/%m/")
    nom_original = models.CharField(max_length=255, blank=True)
    taille = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entite_liee_type", "entite_liee_id"])]

    def __str__(self) -> str:
        return f"{self.type_doc} · {self.nom_original or self.fichier.name}"
