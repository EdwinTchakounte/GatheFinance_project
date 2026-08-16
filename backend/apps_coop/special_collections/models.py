"""Collectes particulières — caisse scolaire & tontine alimentaire.

Ce sont des collectes INDIVIDUELLES par membre (chacun a son propre solde et son
objectif), distinctes de la collecte journalière (``SavingsAccount``) et de
l'épargne classique (``ClassicSavingsAccount``).

Cycle de vie (par membre et par type) :
  1. Le membre envoie une DEMANDE de participation avec un petit formulaire
     (objectif + montant cible + charge utile extensible ``form_payload``).
  2. L'admin VALIDE (ou rejette) la demande.
  3. Une fois validé, le membre peut ALIMENTER son solde :
       • par versement Mobile Money (``Payment`` de type dédié) ;
       • par transfert interne depuis son épargne classique disponible.

Le formulaire est volontairement minimal et stocké en partie dans un JSON
(``form_payload``) pour pouvoir être enrichi plus tard sans migration.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


class SpecialCollectionMembership(TimestampedModel):
    """Participation d'un membre à une collecte particulière (1 par type)."""

    class Type(models.TextChoices):
        CAISSE_SCOLAIRE = "caisse_scolaire", "Caisse scolaire"
        TONTINE_ALIMENTAIRE = "tontine_alimentaire", "Tontine alimentaire"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente de validation"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"
        SUSPENDU = "suspendu", "Suspendu"

    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="special_collections",
    )
    # Cycle d'appartenance : chaque participation vit dans UN cycle (ouvert ou
    # clos). À chaque nouveau cycle, le membre re-demande → nouvelle ligne, solde
    # propre à 0. Le solde d'un cycle clos reste figé (gel + archivage).
    cycle = models.ForeignKey(
        "SpecialCollectionCycle",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    statut = models.CharField(
        max_length=16,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        db_index=True,
    )
    solde = money_field(default=ZERO)

    # ── Formulaire de demande (extensible) ────────────────────────────────────
    objectif = models.TextField(
        help_text="Ce que le membre attend de sa collecte (saisi à la demande)."
    )
    montant_cible = money_field(
        null=True,
        blank=True,
        help_text="Objectif chiffré facultatif renseigné par le membre.",
    )
    form_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Champs additionnels du formulaire (extensible sans migration).",
    )

    # ── Traçabilité de la décision admin ──────────────────────────────────────
    motif_rejet = models.TextField(blank=True, default="")
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="validated_special_collections",
    )
    validated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Participation collecte particulière"
        verbose_name_plural = "Participations collectes particulières"
        constraints = [
            # Une seule participation par membre et par cycle (re-demande =
            # ré-arme la même ligne tant qu'on est dans le même cycle).
            models.UniqueConstraint(
                fields=["member", "cycle"],
                name="uniq_member_special_collection_cycle",
            )
        ]
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.get_type_display()} · {self.member.numero_membre} · {self.statut}"

    @property
    def is_active(self) -> bool:
        """Le membre peut-il verser / transférer sur cette collecte ?

        Il faut être validé ET dans un cycle encore ouvert (un cycle clos est
        gelé : plus aucun mouvement).
        """
        return self.statut == self.Statut.VALIDE and self.cycle.is_open


class SpecialCollectionCycle(TimestampedModel):
    """Cycle d'une collecte particulière (caisse scolaire / tontine alimentaire).

    Un cycle = une période bornée, propre à un type. **Un seul cycle ouvert par
    type** à la fois (contrainte DB partielle). L'admin ouvre un nouveau cycle
    (ce qui clôt le précédent) ; les participants re-demandent pour ce cycle. À
    la clôture, le cycle et ses soldes sont **gelés + archivés** (aucun mouvement
    d'argent automatique — rapprochement géré par l'admin).
    """

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouvert"
        CLOS = "clos", "Clos"

    type = models.CharField(
        max_length=32,
        choices=SpecialCollectionMembership.Type.choices,
        db_index=True,
    )
    nom = models.CharField(
        max_length=120,
        help_text="Libellé du cycle (ex. « Caisse scolaire 2026-2027 »).",
    )
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=8,
        choices=Statut.choices,
        default=Statut.OUVERT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_collection_cycles_created",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_collection_cycles_closed",
    )

    class Meta:
        verbose_name = "Cycle de collecte particulière"
        verbose_name_plural = "Cycles de collectes particulières"
        constraints = [
            # Au plus UN cycle ouvert par type (barrière DB).
            models.UniqueConstraint(
                fields=["type"],
                condition=models.Q(statut="ouvert"),
                name="uniq_open_cycle_per_type",
            )
        ]
        ordering = ["-date_debut", "-id"]

    def __str__(self) -> str:
        return f"{self.get_type_display()} · {self.nom} · {self.statut}"

    @property
    def is_open(self) -> bool:
        return self.statut == self.Statut.OUVERT


class SpecialCollectionTransaction(TimestampedModel):
    """Ledger append-only des mouvements d'une collecte particulière."""

    class TypeOp(models.TextChoices):
        VERSEMENT = "versement", "Versement (Mobile Money)"
        TRANSFERT = "transfert", "Transfert entrant (épargne classique)"

    membership = models.ForeignKey(
        SpecialCollectionMembership,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="special_collection_transactions",
        help_text="Paiement Mobile Money à l'origine ; null pour un transfert interne.",
    )
    type_op = models.CharField(max_length=16, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(
        help_text="Solde de la collecte juste après cette opération."
    )
    libelle = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Libellé lisible (ex. « Transfert depuis épargne classique »).",
    )

    class Meta:
        verbose_name = "Écriture collecte particulière"
        verbose_name_plural = "Écritures collectes particulières"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["membership", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"
