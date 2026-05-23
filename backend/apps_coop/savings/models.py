"""Savings domain — one savings account per member with append-only transactions."""
from __future__ import annotations

from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


class SavingsAccount(TimestampedModel):
    """One savings account per Member (enforced by OneToOne)."""

    member = models.OneToOneField(
        Member,
        on_delete=models.PROTECT,
        related_name="savings_account",
    )
    solde = money_field(default=ZERO)
    date_ouverture = models.DateField()
    taux_interet_applique = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
        help_text="Annual rate, e.g. 0.0350 for 3.5%.",
    )

    class Meta:
        verbose_name = "Compte d'épargne"
        verbose_name_plural = "Comptes d'épargne"

    def __str__(self) -> str:
        return f"Compte de {self.member.numero_membre} · solde={self.solde}"


class SavingsTransaction(TimestampedModel):
    """Append-only ledger of deposits, withdrawals and credited interest."""

    class TypeOp(models.TextChoices):
        DEPOT = "depot", "Dépôt"
        RETRAIT = "retrait", "Retrait"
        INTERET = "interet", "Intérêt"

    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    # FK to Payment is wired *string-style* to avoid a circular import; resolved
    # at migration time once both apps are loaded.
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="savings_transactions",
        help_text="Backing Payment for deposit/withdrawal; null for system-credited interest.",
    )
    type_op = models.CharField(max_length=10, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(help_text="Snapshot of account balance immediately after this row.")
    date = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["account", "-date"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"


class ClassicSavingsConfig(TimestampedModel):
    """Configuration (singleton) du produit **Épargne classique**, éditable par
    l'admin — dissocié de la cotisation/collecte journalière (`SavingsAccount`).

    Les règles métier précises (taux, plafonds, conditions de retrait) seront
    affinées plus tard : on pose ici des paramètres **neutres par défaut**
    (taux 0 %, pas de plafond) que l'admin ajustera.
    """

    SINGLETON_PK = 1

    actif = models.BooleanField(default=True, help_text="Produit ouvert aux dépôts.")
    libelle = models.CharField(max_length=120, default="Épargne classique")
    taux_interet_mensuel = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=0,
        help_text="Ratio mensuel (ex. 0.0100 = 1 %). 0 = pas d'intérêt (règles à définir).",
    )
    depot_min = money_field(default=ZERO, help_text="Montant minimum par dépôt.")
    depot_max = money_field(
        null=True, blank=True, help_text="Plafond par dépôt (vide = aucun plafond)."
    )
    retrait_validation_requise = models.BooleanField(
        default=True, help_text="Retrait soumis à validation de l'administration."
    )

    class Meta:
        verbose_name = "Configuration épargne classique"
        verbose_name_plural = "Configuration épargne classique"

    def __str__(self) -> str:
        return f"Épargne classique · {self.libelle} · actif={self.actif}"

    @classmethod
    def get_solo(cls) -> "ClassicSavingsConfig":
        """Retourne la config unique, la créant avec les défauts si absente."""
        obj, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return obj


class ClassicSavingsAccount(TimestampedModel):
    """Compte d'épargne classique d'un membre — distinct du compte de
    cotisation/collecte journalière (`SavingsAccount`). Créé à la volée au
    premier dépôt."""

    member = models.OneToOneField(
        Member,
        on_delete=models.PROTECT,
        related_name="classic_savings_account",
    )
    solde = money_field(default=ZERO)
    date_ouverture = models.DateField()

    class Meta:
        verbose_name = "Compte épargne classique"
        verbose_name_plural = "Comptes épargne classique"

    def __str__(self) -> str:
        return f"Épargne classique {self.member.numero_membre} · solde={self.solde}"


class ClassicSavingsTransaction(TimestampedModel):
    """Ledger append-only du compte d'épargne classique."""

    class TypeOp(models.TextChoices):
        DEPOT = "depot", "Dépôt"
        RETRAIT = "retrait", "Retrait"
        INTERET = "interet", "Intérêt"

    account = models.ForeignKey(
        ClassicSavingsAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="classic_savings_transactions",
        help_text="Paiement à l'origine du dépôt ; null pour un intérêt système.",
    )
    type_op = models.CharField(max_length=10, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(help_text="Solde du compte juste après cette opération.")
    date = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["account", "-date"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"


class WithdrawalRequest(TimestampedModel):
    """Demande de retrait d'épargne par un membre.

    Le règlement organise la *collecte* (entrées) ; le retrait n'y est pas
    cadré. Politique adoptée : le membre demande un retrait, l'administration
    valide. À l'approbation, le solde est débité (SavingsTransaction `retrait`)
    et l'argent est remis au membre (espèces agence ou payout Mobile Money,
    tracé hors de ce modèle).

    Workflow :
        en_attente → approuvee (solde débité) | rejetee
    """
    from django.conf import settings as _settings

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"

    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        related_name="withdrawal_requests",
    )
    montant = money_field()
    motif = models.TextField(blank=True, help_text="Raison du retrait (renseignée par le membre).")

    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        db_index=True,
    )
    motif_rejet = models.TextField(blank=True)

    # Transaction de débit créée à l'approbation (trace le mouvement de solde).
    transaction = models.OneToOneField(
        "savings.SavingsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_request",
    )

    decide_par = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_decisions",
    )
    date_demande = models.DateTimeField(auto_now_add=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "Demande de retrait"
        verbose_name_plural = "Demandes de retrait"
        indexes = [models.Index(fields=["statut", "-date_demande"])]

    def __str__(self) -> str:
        return f"Retrait {self.montant} · {self.account.member.numero_membre} · {self.statut}"
