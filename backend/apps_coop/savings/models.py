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
