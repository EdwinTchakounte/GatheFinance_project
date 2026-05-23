"""Loans domain — request → loan → installments → repayments.

`LoanRequest` and `Loan` are separated by design: a credit only exists once
the request is approved. Repayment imputation goes through `LoanRepayment`,
which maps a `Payment` row to one or more installments (partial / FIFO logic
implemented in the application service, not in the model).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


PAYMENT_MODALITY_CHOICES = (
    ("journalier",   "Journalier"),
    ("hebdomadaire", "Hebdomadaire"),
    ("mensuel",      "Mensuel"),
)


class LoanRequest(TimestampedModel):
    """Member-submitted credit request.

    Workflow (cf. ``architecture/04-demande-credit.md``) :
      en_attente → en_instruction (paiement frais)
                 → approuvee / rejetee / en_attente_acceptation_membre
                 (décision du président comité)
                 → approuvee / rejetee (réponse du membre à la contre-prop.)
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente (frais à payer)"
        EN_INSTRUCTION = "en_instruction", "En instruction"
        EN_ATTENTE_ACCEPTATION_MEMBRE = "en_attente_acceptation_membre", "Contre-proposition à accepter"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="loan_requests")
    montant_demande = money_field()
    duree_mois = models.PositiveIntegerField(
        help_text="Déduit automatiquement du montant via le tableau de paliers du règlement.",
    )
    modalite_paiement = models.CharField(
        max_length=16,
        choices=PAYMENT_MODALITY_CHOICES,
        default="mensuel",
        help_text="Cadence de remboursement choisie par le membre (Article 8).",
    )
    motif = models.TextField()

    statut = models.CharField(max_length=32, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)
    motif_rejet = models.TextField(blank=True)

    date_soumission = models.DateTimeField(auto_now_add=True)

    # Step B — pre-instruction by the agent staff
    instruit_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_requests_instructed",
    )
    avis_instruction = models.TextField(
        blank=True,
        help_text="Recommandation rédigée par l'agent staff après examen du dossier.",
    )
    scoring = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Score 0-10 attribué par l'agent à l'issue de l'instruction.",
    )

    # Step C/D — decision recorded by the comité chair
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_requests_decided",
        help_text="Président du comité qui a enregistré la décision dans le système.",
    )
    date_decision = models.DateTimeField(null=True, blank=True)
    date_comite = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date effective de la délibération du comité (≠ date de saisie).",
    )
    # `pv_comite` = FK to apps_coop.members.Document; wired below via string ref
    # to avoid a cyclical import at module load.
    pv_comite = models.ForeignKey(
        "members.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_requests_pv",
        help_text="PV signé de la délibération comité, uploadé par le président.",
    )

    # Counter-proposal fields — populated when statut == en_attente_acceptation_membre
    montant_revise = money_field(null=True, blank=True)
    duree_revisee = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-date_soumission"]
        verbose_name = "Demande de crédit"
        verbose_name_plural = "Demandes de crédit"

    def __str__(self) -> str:
        return f"Demande #{self.pk} · {self.member.numero_membre} · {self.montant_demande}"


class Loan(TimestampedModel):
    """Approved credit; backbone for installments, repayments and renewals."""

    class Statut(models.TextChoices):
        ACTIF = "actif", "Actif"
        EN_RETARD = "en_retard", "En retard"
        CLOTURE = "cloture", "Clôturé"
        CONTENTIEUX = "contentieux", "Contentieux"

    loan_request = models.OneToOneField(
        LoanRequest,
        on_delete=models.PROTECT,
        related_name="loan",
    )
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="loans")
    numero_dossier = models.CharField(max_length=32, unique=True, db_index=True)

    montant = money_field()
    taux_interet = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        help_text=(
            "Taux flat appliqué une seule fois sur le montant (Règlement, Article 5). "
            "Par défaut 0.1000 (= 10 % par transaction)."
        ),
    )
    duree_mois = models.PositiveIntegerField(
        help_text="Durée en mois, dérivée du montant via les paliers du règlement (Article 7).",
    )
    modalite_paiement = models.CharField(
        max_length=16,
        choices=PAYMENT_MODALITY_CHOICES,
        default="mensuel",
        help_text="Cadence de remboursement (Article 8) — choix définitif sauf demande écrite.",
    )

    date_decaissement = models.DateField()
    date_premiere_echeance = models.DateField()

    montant_total_du = money_field(help_text="Principal + total interests over full term.")
    solde_restant = money_field()

    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.ACTIF, db_index=True)

    # Un crédit issu d'une reconduction ne peut pas être reconduit à son tour :
    # la reconduction n'a lieu qu'une seule fois par crédit (règle coop).
    issu_reconduction = models.BooleanField(
        default=False,
        help_text="True si ce crédit est né d'une reconduction — non reconductible à nouveau.",
    )

    # Mise en demeure (Article 13) — émise par l'administration sur un crédit
    # en retard ou en contentieux, avant poursuites éventuelles.
    mise_en_demeure_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la dernière mise en demeure envoyée (Article 13).",
    )
    mise_en_demeure_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Nombre de mises en demeure émises pour ce crédit.",
    )

    class Meta:
        ordering = ["-date_decaissement"]
        indexes = [models.Index(fields=["member", "statut"])]

    def __str__(self) -> str:
        return f"{self.numero_dossier} · {self.member.numero_membre} · {self.statut}"


class LoanGuarantee(TimestampedModel):
    """Collateral attached to a Loan (cash deposit, vehicle, real estate, surety)."""

    class TypeGarantie(models.TextChoices):
        CAUTION = "caution", "Caution"
        BIEN_IMMOBILIER = "bien_immobilier", "Bien immobilier"
        VEHICULE = "vehicule", "Véhicule"
        DEPOT_GARANTIE = "depot_garantie", "Dépôt de garantie"

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="guarantees")
    type_garantie = models.CharField(max_length=20, choices=TypeGarantie.choices)
    description = models.TextField(blank=True)
    valeur_estimee = money_field(default=ZERO)

    class Meta:
        verbose_name = "Garantie"
        verbose_name_plural = "Garanties"

    def __str__(self) -> str:
        return f"{self.type_garantie} ({self.valeur_estimee})"


class LoanInstallment(TimestampedModel):
    """One row per scheduled monthly payment of a Loan."""

    class Statut(models.TextChoices):
        A_VENIR = "a_venir", "À venir"
        PAYEE = "payee", "Payée"
        EN_RETARD = "en_retard", "En retard"
        PARTIELLE = "partielle", "Partielle"

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    numero_echeance = models.PositiveIntegerField()
    date_echeance = models.DateField(db_index=True)
    montant_capital = money_field()
    montant_interets = money_field()
    montant_total = money_field()
    montant_paye = money_field(default=ZERO)
    # Pénalité Article 12 — 50 % des intérêts proratisés sur la somme manquante.
    # Posée par le cron suivi_retards_quotidien au passage en `en_retard`.
    # Idempotence : ``penalite_appliquee_at`` non-null = déjà calculée, ne pas
    # ré-appliquer aux passages suivants du cron.
    montant_penalite = money_field(default=ZERO)
    penalite_appliquee_at = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.A_VENIR, db_index=True)

    class Meta:
        ordering = ["loan", "numero_echeance"]
        constraints = [
            models.UniqueConstraint(fields=["loan", "numero_echeance"], name="loan_installment_unique"),
        ]

    def __str__(self) -> str:
        return f"#{self.numero_echeance} {self.loan.numero_dossier} · {self.date_echeance} · {self.statut}"


class LoanRepayment(TimestampedModel):
    """Maps a Payment to one Installment with the imputed amount (N-N via this table)."""

    installment = models.ForeignKey(LoanInstallment, on_delete=models.PROTECT, related_name="repayments")
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="loan_repayments",
    )
    montant_impute = money_field()
    date = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"

    def __str__(self) -> str:
        return f"{self.montant_impute} → échéance #{self.installment.numero_echeance}"


class LoanRenewal(TimestampedModel):
    """Renewal/rollover request of an existing loan."""

    class Statut(models.TextChoices):
        DEMANDEE = "demandee", "Demandée"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"

    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="renewals")
    nouvelle_duree_mois = models.PositiveIntegerField(
        help_text=(
            "Durée additionnelle (Règlement, Article 10) — fixée à 1 mois par défaut. "
            "Conservée modifiable pour rétro-compat."
        ),
        default=1,
    )
    interets_au_comptant = models.BooleanField(
        default=False,
        help_text=(
            "Si True, les intérêts sont versés cash à la reconduction (taux 10 %). "
            "Sinon ils sont reportés avec le capital (taux 15 %). Article 11."
        ),
    )
    frais_reconduction_payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="renewal_fees",
    )
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.DEMANDEE, db_index=True)
    date_demande = models.DateTimeField(auto_now_add=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "Reconduction"
        verbose_name_plural = "Reconductions"

    def __str__(self) -> str:
        return f"Reconduction {self.loan.numero_dossier} · {self.statut}"
