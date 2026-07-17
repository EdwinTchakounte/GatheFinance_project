"""Payments domain — every money flow (deposit, fee, repayment, disbursement)
goes through one `Payment` row. Source is currently `manuel` or `mobile_money`;
adding a new gateway is just a new enum value plus a provider implementation.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


class FeeType(TimestampedModel):
    """Catalogue of recurring administrative fees the cooperative charges.

    The amount is stored here so updating a fee never requires a migration.
    """

    class Code(models.TextChoices):
        INSCRIPTION = "INSCRIPTION", "Frais d'inscription"
        ADHESION = "ADHESION", "Frais d'adhésion"
        DEMANDE_CREDIT = "DEMANDE_CREDIT", "Frais de demande de crédit"
        RECONDUCTION = "RECONDUCTION", "Frais de reconduction"
        CARNET = "CARNET", "Frais de carnet"

    code = models.CharField(max_length=24, choices=Code.choices, unique=True)
    libelle = models.CharField(max_length=120)
    montant = money_field(default=ZERO)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Type de frais"
        verbose_name_plural = "Types de frais"

    def __str__(self) -> str:
        return f"{self.code} · {self.montant}"


class RateParam(TimestampedModel):
    """Catalogue des **taux** métier modifiables par l'admin (BR2).

    Pendant FeeType (montants fixes en FCFA), mais pour les pourcentages : taux
    d'intérêt crédit, intérêt épargne mensuel, taux de reconduction, pénalité.
    Stockés en base → un admin les ajuste sans déploiement ni migration.

    ``valeur`` est un ratio (ex. ``0.10`` = 10 %). Les défauts réglementaires
    vivent dans ``loans/terms.py`` et ``savings/cutoff.py`` et servent de
    fallback sûr (voir ``payments.rates.get_rate``).
    """

    class Code(models.TextChoices):
        LOAN_INTEREST = "LOAN_INTEREST", "Taux d'intérêt crédit (par transaction)"
        SAVINGS_INTEREST_MONTHLY = (
            "SAVINGS_INTEREST_MONTHLY",
            "Taux d'intérêt épargne (mensuel)",
        )
        RENEWAL_CASH = "RENEWAL_CASH", "Reconduction — intérêts au comptant"
        RENEWAL_DEFERRED = "RENEWAL_DEFERRED", "Reconduction — intérêts reportés"
        LATE_PENALTY = "LATE_PENALTY", "Pénalité de non-versement"
        # Frais de transaction en % prélevés EN PLUS du montant sur chaque
        # versement Mobile Money (le membre paie montant + frais ; le compte est
        # crédité du montant de base). Défaut 0 → aucun frais tant que non réglé.
        TRANSACTION_FEE = "TRANSACTION_FEE", "Frais de transaction sur versement (%)"

    code = models.CharField(max_length=32, choices=Code.choices, unique=True)
    libelle = models.CharField(max_length=120)
    valeur = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text="Ratio entre 0 et 1 (ex. 0.1000 pour 10 %).",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Taux métier"
        verbose_name_plural = "Taux métier"

    def __str__(self) -> str:
        return f"{self.code} · {self.valeur}"


class Payment(TimestampedModel):
    """Pivot entity for every money movement. Mobile Money fields are nullable
    so manual cash entries (recorded by an admin at the agency) work too.
    """

    class Type(models.TextChoices):
        EPARGNE = "epargne", "Épargne"
        EPARGNE_CLASSIQUE = "epargne_classique", "Épargne classique"
        FRAIS_INSCRIPTION = "frais_inscription", "Frais d'inscription"
        FRAIS_ADHESION = "frais_adhesion", "Frais d'adhésion"
        FRAIS_DEMANDE_CREDIT = "frais_demande_credit", "Frais de demande de crédit"
        FRAIS_RECONDUCTION = "frais_reconduction", "Frais de reconduction"
        FRAIS_CARNET = "frais_carnet", "Frais de carnet"
        REMBOURSEMENT = "remboursement", "Remboursement"
        DECAISSEMENT = "decaissement", "Décaissement"

    class Source(models.TextChoices):
        MANUEL = "manuel", "Saisie agence"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        # Porte des frais d'étude (2026) — 3e canal : le membre règle en
        # prélevant sur son épargne classique. Pas d'argent entrant : c'est un
        # transfert interne, validé d'emblée (aucun encaissement à attendre).
        DEDUCTION_EPARGNE = "deduction_epargne", "Déduction sur épargne classique"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        VALIDE = "valide", "Validé"
        REJETE = "rejete", "Rejeté"

    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name="payments")
    montant = money_field()
    # Frais de transaction (%) encaissés EN PLUS du montant (RateParam
    # TRANSACTION_FEE). Le membre paie `montant + frais_transaction` via Tara ;
    # les hooks métier créditent uniquement `montant`. 0 = pas de frais.
    frais_transaction = money_field(default=0)
    type = models.CharField(max_length=24, choices=Type.choices, db_index=True)
    source = models.CharField(max_length=24, choices=Source.choices, db_index=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)

    # Optional links — set when the payment is imputed to a credit
    loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="related_payments",
    )
    loan_installment = models.ForeignKey(
        "loans.LoanInstallment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="related_payments",
    )

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_validated",
    )
    date_versement = models.DateTimeField(db_index=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    # External gateway tracking — only filled for `source = mobile_money`
    provider_code = models.CharField(
        max_length=24,
        blank=True,
        help_text="Provider key (e.g. 'tara'). Empty for manual entries.",
    )
    reference_externe = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Provider transaction id once initiated.",
    )
    idempotency_key = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Prevents duplicate gateway init when the user retries.",
    )
    gateway_initiated_at = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True)

    # CH-3 (refonte 2026) — Épargne classique : sous-canal « placement ».
    # Vrai uniquement si type == EPARGNE_CLASSIQUE ET que le membre coche
    # « placer ce dépôt » sur le formulaire. Posé à la création du Payment et
    # propagé au hook `_hook_classic_savings_deposit`, qui pose à son tour
    # `placement_unlock_date` sur la transaction ledger.
    is_placement = models.BooleanField(
        default=False,
        help_text=(
            "Sous-canal épargne classique : True = placement bloqué 12 mois "
            "(intérêt mensuel), False = libre (retrait à tout moment)."
        ),
    )

    # LOT 2 (refonte 2026) — multi-jours pré-payé sur la collecte journalière.
    # Pertinent uniquement pour ``type = EPARGNE`` (collecte) ; ignoré sinon.
    # 1 = paiement standard d'1 jour. N > 1 = paiement couvrant N jours
    # (ex. 5000 FCFA pour 5 jours à 1000/j). Plafonné côté UI à
    # ``collecte.prepay.max_days`` (défaut 30).
    nb_jours_couverts = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "Multi-jours pré-payé pour la collecte (refonte 2026). "
            "Défaut 1 = paiement standard."
        ),
    )

    class Meta:
        ordering = ["-date_versement", "-id"]
        indexes = [
            models.Index(fields=["statut", "source"]),
            models.Index(fields=["member", "-date_versement"]),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} · {self.type} · {self.montant} · {self.statut}"


class PaymentProof(TimestampedModel):
    """Receipt or screenshot attached to a Payment (mostly for manual entries)."""

    class TypeDocument(models.TextChoices):
        RECU = "recu", "Reçu"
        CAPTURE = "capture", "Capture d'écran"
        RIB = "rib", "RIB / référence"
        AUTRE = "autre", "Autre"

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="proofs")
    fichier = models.FileField(upload_to="coop/payments/%Y/%m/")
    type_document = models.CharField(max_length=10, choices=TypeDocument.choices)
    taille = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Justificatif de paiement"
        verbose_name_plural = "Justificatifs de paiement"

    def __str__(self) -> str:
        return f"{self.type_document} pour Payment #{self.payment_id}"


# --- Invalidation du cache des taux ----------------------------------------
# get_rate (apps_coop.payments.rates) mémoïse chaque taux ; on le purge dès
# qu'un admin édite/supprime un RateParam (propagation immédiate sur le worker
# éditeur ; les autres suivent via le TTL du cache).
from django.db.models.signals import post_delete, post_save  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver([post_save, post_delete], sender=RateParam)
def _invalidate_rate_cache(sender, instance, **kwargs):  # noqa: ANN001, ARG001, ANN201
    from django.core.cache import cache

    from .rates import rate_cache_key

    cache.delete(rate_cache_key(instance.code))
