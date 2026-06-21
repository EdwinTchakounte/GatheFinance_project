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
        # Refonte 2026 (LOT 11 / §8) — Bénéficiaire micro-crédit campagne :
        # accès au crédit campagne uniquement, pas d'épargne, pas de saisie
        # possible. Peut basculer ``ACTIF`` après paiement des frais
        # d'inscription (Q15).
        TEMPORAIRE = "temporaire", "Temporaire (micro-crédit campagne)"

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

    # A2 — Réinscription annuelle (alerte douce, non bloquante).
    # ``date_derniere_reinscription`` est la date à partir de laquelle on
    # compte les 12 mois jusqu'à la prochaine échéance. Initialement =
    # ``date_adhesion`` (cf. migration de backfill 0004).
    date_derniere_reinscription = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date de référence pour le calcul de l'anniversaire annuel. "
            "Mise à jour à chaque re-souscription confirmée par l'admin."
        ),
    )

    # LOT 1 (refonte 2026) — BRC validation
    # Sécurité crédit (§7.1 BUSINESS_RULES_2026) : un membre ancien peut
    # emprunter "sans doute et garantie" UNIQUEMENT si son statut BRC
    # (Broad Range Consulting) a été validé par un admin sur la base d'un
    # justificatif uploadé. Le flag est posé par
    # ``services.validate_brc_document`` une fois le doc validé.
    is_brc_member = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True si le justificatif BRC a été validé par un admin.",
    )
    brc_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de validation du statut BRC (par admin).",
    )
    brc_validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brc_validations",
        help_text="Admin ayant validé le statut BRC du membre.",
    )

    # LOT 11 (refonte 2026) — Voie 3 MICROCAMPAIGN.
    # Posé à la création d'un Member ``TEMPORAIRE`` issu d'une campagne
    # micro-crédit. String ref pour éviter un cycle loans ↔ members.
    microcampaign = models.ForeignKey(
        "loans.MicrocreditCampaign",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="beneficiaires",
        help_text=(
            "Campagne d'origine pour un Member TEMPORAIRE (§8 BUSINESS_RULES_2026). "
            "NULL pour les adhérents standards."
        ),
    )

    class Meta:
        ordering = ["-date_adhesion"]
        indexes = [models.Index(fields=["statut", "-date_adhesion"])]

    def __str__(self) -> str:
        return f"{self.numero_membre} · {self.prenom} {self.nom}"

    @property
    def seniority_months(self) -> int:
        """Nombre de mois écoulés depuis ``date_adhesion`` (entier, plancher 0).

        Utilisé pour vérifier l'éligibilité "Ancien" (§3 BUSINESS_RULES_2026).
        Calcul déterministe à base de ``timezone.localdate()`` — pas de
        ``relativedelta`` pour rester hors-fuseau.
        """
        from django.utils import timezone

        if not self.date_adhesion:
            return 0
        today = timezone.localdate()
        delta = (today.year - self.date_adhesion.year) * 12 + (
            today.month - self.date_adhesion.month
        )
        # Si on n'a pas encore atteint le jour-anniversaire du mois, on
        # décrémente d'un mois pour rester strict.
        if today.day < self.date_adhesion.day:
            delta -= 1
        return max(0, delta)

    @property
    def is_senior(self) -> bool:
        """True si l'ancienneté ≥ ``seniority.threshold_months`` (défaut 12).

        Critère "Ancien" (§3) qui débloque les voies d'éligibilité crédit
        direct (avec BRC) ou rôle d'avaliste pour un nouvel adhérent.
        Le seuil est tunable via AppSetting — pas de hardcode.
        """
        from apps_coop.audit.services import get_int_setting

        threshold = get_int_setting("seniority.threshold_months", 12)
        return self.seniority_months >= threshold

    @property
    def is_lender(self) -> bool:
        """True si le membre a une convention prêteur active (refonte 2026 §6)."""
        try:
            consent = self.lender_consent  # noqa: F841 (raises if absent)
        except Exception:  # noqa: BLE001 — pas de consent posé
            return False
        return consent.revoked_at is None

    @property
    def capacite_pretable(self):
        """Capacité prêtable du membre (refonte 2026 §6 — Épargne-prêteur).

        Retourne ``Decimal(0)`` si pas de consentement actif. Sinon :
          • Mode A (global) : ``solde_epargne_classique - tranches_engagees``
          • Mode B (tranches) : somme des tranches en statut ``DISPONIBLE``

        Note : on lit l'épargne **classique** (``classic_savings_account``),
        pas la collecte journalière (qui est restituée fin de mois).
        """
        from decimal import Decimal

        from django.db.models import Sum

        if not self.is_lender:
            return Decimal("0.00")

        from apps_coop.savings.models import LenderTranche

        consent = self.lender_consent
        if consent.is_global:
            try:
                solde = Decimal(self.classic_savings_account.solde)
            except Exception:  # noqa: BLE001 — pas de compte épargne classique
                return Decimal("0.00")
            engaged = LenderTranche.objects.filter(
                member=self,
                statut=LenderTranche.Statut.ENGAGEE,
            ).aggregate(s=Sum("montant"))["s"] or Decimal("0.00")
            return max(Decimal("0.00"), solde - Decimal(engaged))
        # Mode B — somme des tranches disponibles
        dispo = LenderTranche.objects.filter(
            member=self,
            statut=LenderTranche.Statut.DISPONIBLE,
        ).aggregate(s=Sum("montant"))["s"] or Decimal("0.00")
        return Decimal(dispo)

    @property
    def prochaine_reinscription_due(self):
        """Date à laquelle la prochaine réinscription est exigible (anniversaire).

        Retourne ``None`` si ``date_derniere_reinscription`` n'est pas définie
        (cas legacy avant migration). Le calcul utilise +365 jours (et non
        ``relativedelta(years=1)``) pour rester déterministe et hors-fuseau.
        """
        from datetime import timedelta

        base = self.date_derniere_reinscription
        if base is None:
            return None
        return base + timedelta(days=365)


class MembershipRequest(TimestampedModel):
    """Public adhesion form submission, instructed by an admin.

    Created by the public ``POST /api/forms/adhesion/`` endpoint (anonymous,
    captcha-protected, rate-limited). Decision is taken from the Django admin
    by an internal user with the ``coop_admin`` group permission, which
    triggers ``services.approve_membership_request`` to create the User +
    Member + SavingsAccount atomically.

    Les champs collectés sont alignés sur l'Article 2 du Règlement Intérieur.

    Pièces téléversées par le demandeur lui-même au moment de la soumission
    (mobile / vitrine) : CNI recto, CNI verso, plan de localisation, photo
    d'identité. Les pièces sont obligatoires côté serializer mais nullable au
    niveau du modèle pour préserver l'historique des demandes legacy créées
    avant cette évolution. L'admin peut compléter / remplacer ces pièces
    pendant l'entretien (Article 3) via le Django admin.
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

    # CH-4 — Champs supplémentaires alimentés par le schéma de formulaire
    # dynamique actif au moment de la soumission. Les colonnes hard-codées
    # ci-dessus restent la source de vérité pour les champs « historiques » ;
    # tout champ ajouté par l'admin via FormSchema atterrit ici.
    extra_payload = models.JSONField(
        default=dict, blank=True,
        help_text="Champs FormSchema additionnels (id_champ → valeur).",
    )
    form_schema_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Version du FormSchema 'adhesion' actif lors de la soumission.",
    )

    # Pièces téléversées par le demandeur (mobile / vitrine).
    # Le serializer public les rend obligatoires, mais on garde
    # ``null=True, blank=True`` ici pour ne pas casser la migration sur les
    # demandes legacy (avant cette évolution) qui n'ont aucun fichier.
    cni_recto = models.FileField(
        upload_to="coop/adhesion/cni/%Y/%m/",
        null=True,
        blank=True,
        help_text="CNI face recto (image ou PDF).",
    )
    cni_verso = models.FileField(
        upload_to="coop/adhesion/cni/%Y/%m/",
        null=True,
        blank=True,
        help_text="CNI face verso (image ou PDF).",
    )
    plan_localisation = models.FileField(
        upload_to="coop/adhesion/plan/%Y/%m/",
        null=True,
        blank=True,
        help_text="Plan ou photo du domicile (image ou PDF).",
    )
    photo_identite = models.ImageField(
        upload_to="coop/adhesion/photo/%Y/%m/",
        null=True,
        blank=True,
        help_text="Selfie / photo portrait du demandeur.",
    )

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


class BRCDocument(TimestampedModel):
    """Justificatif BRC (Broad Range Consulting) uploadé par un membre.

    Refonte 2026 (§7.1 BUSINESS_RULES_2026) : pour pouvoir emprunter des
    grosses sommes "sans doute et garantie", un membre ancien doit prouver
    qu'il est client BRC (le cabinet de fiscalité partenaire). Le flow :

      1. Membre upload un justificatif (PDF / image) via le portail/mobile
         → ``BRCDocument`` créé en ``EN_ATTENTE``
      2. Admin examine le doc dans le back-office
      3. Admin **valide** → ``Member.is_brc_member = True``
         OU admin **rejette** avec motif → membre peut re-uploader

    Modèle dédié (vs réutiliser ``Document``) car on garde l'historique :
    un membre peut avoir plusieurs ``BRCDocument`` (1 rejeté + 1 validé),
    et chaque ligne porte sa propre piste audit (qui, quand, motif).
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente de validation"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"

    member = models.ForeignKey(
        "Member",
        on_delete=models.CASCADE,
        related_name="brc_documents",
    )
    fichier = models.FileField(upload_to="coop/brc/%Y/%m/")
    nom_original = models.CharField(max_length=255, blank=True)
    taille = models.PositiveIntegerField(default=0, help_text="Taille du fichier en octets.")

    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        db_index=True,
    )
    motif_rejet = models.TextField(
        blank=True,
        help_text="Motif fourni par l'admin en cas de rejet du justificatif.",
    )

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="brc_documents_decided",
        help_text="Admin ayant validé ou rejeté le document.",
    )
    validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la décision admin (validation ou rejet).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Justificatif BRC"
        verbose_name_plural = "Justificatifs BRC"
        indexes = [models.Index(fields=["member", "statut"])]

    def __str__(self) -> str:
        return f"BRC {self.member.numero_membre} · {self.statut}"


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

    # CH-5 — Identifie de quel champ du FormSchema vient l'upload, pour permettre
    # à l'admin de retrouver "le CGA" / "le CFP" / "la CNI" sans relire le JSON.
    # Vide pour les uploads BRC/historiques (rétro-compat).
    schema_field_id = models.CharField(
        max_length=80,
        blank=True,
        db_index=True,
        help_text=(
            "Identifiant du champ FormSchema source (ex. 'cga_attestation'). "
            "Vide pour les uploads historiques."
        ),
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entite_liee_type", "entite_liee_id"]),
            models.Index(fields=["entite_liee_type", "entite_liee_id", "schema_field_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.type_doc} · {self.nom_original or self.fichier.name}"


class PasswordResetCode(TimestampedModel):
    """OTP à 6 chiffres pour le flow "mot de passe oublié" (mobile + portail).

    Stocke un hash SHA-256 du code clair (jamais le code en clair). Un seul
    code actif par utilisateur à la fois : la demande d'un nouveau code
    invalide les précédents. Anti-bruteforce : ``attempts`` plafonné à 5,
    au-delà le code est marqué consommé. Expire 15 minutes après émission.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_codes",
    )
    code_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hex du code clair (6 chiffres). Jamais le code lui-même.",
    )
    expires_at = models.DateTimeField(
        help_text="Au-delà : code invalide même si non utilisé.",
    )
    used_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Posé à la consommation (succès OU 5 essais échoués).",
    )
    attempts = models.PositiveSmallIntegerField(
        default=0,
        help_text="Nombre d'essais infructueux. ≥ 5 → code consumé.",
    )
    ip_request = models.GenericIPAddressField(null=True, blank=True)
    ip_confirm = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "used_at"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self) -> str:
        state = "utilisé" if self.used_at else ("expiré" if self.is_expired else "valide")
        return f"PasswordResetCode({self.user_id}) · {state}"

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.used_at is not None or self.attempts >= 5
