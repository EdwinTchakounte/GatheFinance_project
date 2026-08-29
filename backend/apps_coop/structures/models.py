"""Structures employeur & paie des employés (2026-08).

L'admin crée une **Structure** (employeur), y rattache des employés (des membres
existants) avec leur fiche d'attribution et leur montant de paie, approvisionne
la **cagnotte** de la structure, puis **verse les paies** dans l'épargne classique
LIBRE de chaque employé (retirable normalement). La cagnotte est débitée à la
paie (refus si insuffisante).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


class Structure(TimestampedModel):
    """Employeur payant ses salariés via la coopérative. Possède une cagnotte
    (compte propre) approvisionnée par l'employeur, débitée à chaque paie."""

    class Statut(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOTUREE = "cloturee", "Clôturée"

    nom = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    # Cagnotte de l'employeur (compte propre à la structure).
    solde = money_field(default=ZERO)
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIVE, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structures_created",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Structure (employeur)"
        verbose_name_plural = "Structures (employeurs)"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.nom} · {self.statut}"

    @property
    def is_active(self) -> bool:
        return self.statut == self.Statut.ACTIVE


class StructureEmployee(TimestampedModel):
    """Un membre rattaché à une structure comme employé (poste + paie)."""

    structure = models.ForeignKey(
        Structure, on_delete=models.CASCADE, related_name="employees"
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="structure_employments"
    )
    poste = models.CharField(max_length=120, blank=True, default="")
    # Fiche d'attribution (missions, remarques). Libre.
    attribution = models.TextField(blank=True, default="")
    montant_paie = money_field(default=ZERO)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Employé rattaché"
        verbose_name_plural = "Employés rattachés"
        constraints = [
            models.UniqueConstraint(
                fields=["structure", "member"], name="uniq_structure_member"
            )
        ]
        ordering = ["member__nom", "member__prenom"]

    def __str__(self) -> str:
        return f"{self.member.numero_membre} · {self.poste} · {self.montant_paie}"


class PayrollRun(TimestampedModel):
    """Un lot de paie : versement des salaires de tous les employés actifs d'une
    structure pour une période donnée."""

    structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, related_name="payroll_runs"
    )
    periode = models.CharField(
        max_length=60, help_text="Libellé de période (ex. « Août 2026 »)."
    )
    total_verse = money_field(default=ZERO)
    employes_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_runs_created",
    )

    class Meta:
        verbose_name = "Lot de paie"
        verbose_name_plural = "Lots de paie"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.structure_id} · {self.periode} · {self.total_verse}"


class StructureTransaction(TimestampedModel):
    """Ledger append-only de la cagnotte d'une structure."""

    class TypeOp(models.TextChoices):
        APPROVISIONNEMENT = "approvisionnement", "Approvisionnement (entrée)"
        VERSEMENT_PAIE = "versement_paie", "Versement de paie (sortie)"
        RETRAIT_FONDS = "retrait_fonds", "Retrait de fonds (sortie)"
        AJUSTEMENT = "ajustement", "Ajustement"

    structure = models.ForeignKey(
        Structure, on_delete=models.PROTECT, related_name="transactions"
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structure_transactions",
        help_text="Employé concerné (pour un versement de paie).",
    )
    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="structure_transactions",
    )
    # Qui a effectué l'opération (admin) — traçabilité affichée à l'employé.
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="structure_actions",
    )
    type_op = models.CharField(max_length=20, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(help_text="Solde de la cagnotte après l'opération.")
    date = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Date effective (antidatable). Null → created_at.",
    )
    libelle = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        verbose_name = "Écriture de structure"
        verbose_name_plural = "Écritures de structures"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["structure", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"

    @property
    def date_effective(self):
        return self.date or self.created_at
