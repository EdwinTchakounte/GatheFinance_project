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
        TONTINE_ALIMENTAIRE = "tontine_alimentaire", "Tontine"

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

    Un cycle = une collecte concrète, propre à un type. **Plusieurs collectes
    peuvent être ouvertes simultanément pour un même type** (ex. deux tontines
    en parallèle) : l'admin crée chaque collecte avec son titre, son montant
    minimal par versement et ses informations, et la clôture individuellement.
    Un membre peut participer à plusieurs collectes du même type (une
    participation par cycle). À la clôture, le cycle et ses soldes sont **gelés
    + archivés** (aucun mouvement d'argent automatique — rapprochement admin).
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
        help_text="Titre de la collecte (ex. « Tontine des fêtes 2026 », « Caisse scolaire »).",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="Informations complémentaires (règles, dates clés, modalités).",
    )
    # Plancher par versement : chaque dépôt du membre doit être ≥ ce montant.
    # 0 = pas de plancher spécifique (le minimum global 1000 s'applique ailleurs).
    montant_minimal = money_field(
        default=ZERO,
        help_text="Montant minimal par versement (plancher). 0 = pas de plancher.",
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
        # 2026-08 : PLUSIEURS collectes ouvertes par type sont désormais
        # autorisées (ex. deux tontines simultanées). La contrainte historique
        # « un seul cycle ouvert par type » a été retirée.
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
        # Versement saisi en agence (cash-in admin) ou reprise d'historique
        # antidatée — pas de Payment Mobile Money associé.
        MANUEL = "manuel", "Versement manuel (agence / reprise)"
        # Décaissement : sortie d'argent du solde du participant — vers son
        # épargne classique OU en espèces à l'agence.
        RETRAIT = "retrait", "Retrait / décaissement"

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
    # Carnet (typé tontine/caisse) auquel l'écriture s'impute. Null toléré si le
    # membre n'a pas (encore) de carnet de ce type — imputation best-effort.
    booklet_order = models.ForeignKey(
        "members.BookletOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_collection_transactions",
    )
    type_op = models.CharField(max_length=16, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(
        help_text="Solde de la collecte juste après cette opération."
    )
    # Date EFFECTIVE de l'écriture (peut être antidatée). Null sur les lignes
    # historiques → on retombe sur ``created_at`` pour le tri/l'affichage.
    date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Date effective (antidatable). Null → created_at.",
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

    @property
    def date_effective(self):
        """Date effective de l'écriture (antidatée si posée, sinon created_at)."""
        return self.date or self.created_at


# ═══════════════════════════════════════════════════════════════════════════
# Tontine GROUPE (réunion de quartier) — 2026-08
#
# Distincte des collectes individuelles ci-dessus : la RÉUNION a SON PROPRE
# COMPTE (cagnotte partagée), un roster de membres défini par l'admin à la
# création, et des rôles (président / trésorier). Le trésorier/président
# désigne un bénéficiaire et lui verse un montant (fixé, pas forcément le
# total) depuis la cagnotte ; la réunion peut aussi PRÊTER à un membre.
# Visibilité : seuls les membres du groupe le voient côté mobile.
# ═══════════════════════════════════════════════════════════════════════════
class GroupTontine(TimestampedModel):
    """Réunion de cotisation de groupe (tontine de quartier) avec cagnotte."""

    class Statut(models.TextChoices):
        OUVERT = "ouvert", "Ouverte"
        CLOS = "clos", "Clôturée"

    nom = models.CharField(max_length=120, help_text="Nom de la réunion / du groupe.")
    description = models.TextField(blank=True, default="")
    # Cagnotte de la réunion (compte propre au groupe, distinct des membres).
    solde = money_field(default=ZERO)
    # Cotisation suggérée par tour (indicatif, éditable). 0 = libre.
    montant_cotisation = money_field(default=ZERO)
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
        related_name="group_tontines_created",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_tontines_closed",
    )

    class Meta:
        verbose_name = "Tontine de groupe"
        verbose_name_plural = "Tontines de groupe"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.nom} · {self.statut}"

    @property
    def is_open(self) -> bool:
        return self.statut == self.Statut.OUVERT


class GroupTontineRole(TimestampedModel):
    """Rôle PERSONNALISÉ d'une réunion, avec les actions qui lui sont rattachées.

    Les 3 rôles intégrés (président / trésorier / membre) restent portés par
    ``GroupTontineMember.Role``. Ici l'admin ou le président peut créer des rôles
    SUR MESURE, propres à la réunion (ex. « Secrétaire », « Commissaire »), en
    cochant les actions permises. Un membre porteur d'un rôle custom CUMULE ses
    actions par-dessus celles de son rôle intégré. Le président garde toujours
    TOUTES les actions.

    Les booléens = catalogue d'actions habilitables dans la réunion.
    """

    group = models.ForeignKey(
        GroupTontine, on_delete=models.CASCADE, related_name="custom_roles"
    )
    nom = models.CharField(max_length=60, help_text="Nom du rôle (ex. « Secrétaire »).")
    # Actions rattachées (catalogue).
    can_manage_funds = models.BooleanField(
        default=False, help_text="Verser à un bénéficiaire (payout)."
    )
    can_grant_loan = models.BooleanField(
        default=False, help_text="Accorder un prêt de la cagnotte."
    )
    can_manage_roster = models.BooleanField(
        default=False, help_text="Ajouter/retirer des membres et changer les rôles."
    )
    can_record_cotisation = models.BooleanField(
        default=False, help_text="Enregistrer des cotisations."
    )
    can_close = models.BooleanField(
        default=False, help_text="Clôturer la réunion."
    )

    class Meta:
        verbose_name = "Rôle personnalisé de réunion"
        verbose_name_plural = "Rôles personnalisés de réunion"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "nom"], name="uniq_group_tontine_role_name"
            )
        ]
        ordering = ["nom"]

    # Attributs du catalogue d'actions (source de vérité pour l'agrégation).
    ACTION_FIELDS = (
        "can_manage_funds",
        "can_grant_loan",
        "can_manage_roster",
        "can_record_cotisation",
        "can_close",
    )

    def as_permissions(self) -> dict:
        return {f: bool(getattr(self, f)) for f in self.ACTION_FIELDS}

    def __str__(self) -> str:
        return f"{self.nom} · {self.group_id}"


class GroupTontineMember(TimestampedModel):
    """Appartenance d'un membre à une réunion, avec son rôle (revotable)."""

    class Role(models.TextChoices):
        PRESIDENT = "president", "Président"
        TRESORIER = "tresorier", "Trésorier"
        MEMBRE = "membre", "Membre"

    group = models.ForeignKey(
        GroupTontine, on_delete=models.CASCADE, related_name="members"
    )
    member = models.ForeignKey(
        Member, on_delete=models.CASCADE, related_name="group_tontine_memberships"
    )
    role = models.CharField(
        max_length=12, choices=Role.choices, default=Role.MEMBRE, db_index=True
    )
    # Rôle personnalisé OPTIONNEL — cumule ses actions par-dessus le rôle intégré.
    custom_role = models.ForeignKey(
        GroupTontineRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Membre de tontine de groupe"
        verbose_name_plural = "Membres de tontines de groupe"
        constraints = [
            models.UniqueConstraint(
                fields=["group", "member"], name="uniq_group_tontine_member"
            )
        ]
        ordering = ["role", "member__nom", "member__prenom"]

    def __str__(self) -> str:
        return f"{self.member.numero_membre} · {self.role} · {self.group_id}"


class GroupTontineLoan(TimestampedModel):
    """Prêt accordé par la réunion à l'un de ses membres (depuis la cagnotte)."""

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        SOLDE = "solde", "Soldé"

    group = models.ForeignKey(
        GroupTontine, on_delete=models.PROTECT, related_name="loans"
    )
    member = models.ForeignKey(
        Member, on_delete=models.PROTECT, related_name="group_tontine_loans"
    )
    montant = money_field()
    solde_restant = money_field()
    # Avaliste de la réunion — PUREMENT INFORMATIF : sert seulement à identifier
    # « à qui se rapporter » (activité entre personnes qui se connaissent). AUCUN
    # rapport avec l'avaliste crédit de la coopérative (pas de gel, pas de
    # garantie, pas d'impact financier). Soit un membre du roster, soit un nom
    # libre si la personne est hors réunion.
    avaliste = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_tontine_loans_backed",
        help_text="Avaliste (informatif) — membre du roster, si applicable.",
    )
    avaliste_nom = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Avaliste (informatif) — nom libre si hors réunion.",
    )
    statut = models.CharField(
        max_length=10,
        choices=Statut.choices,
        default=Statut.EN_COURS,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_tontine_loans_granted",
    )

    class Meta:
        verbose_name = "Prêt de tontine de groupe"
        verbose_name_plural = "Prêts de tontines de groupe"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"Prêt {self.montant} → {self.member_id} (reste {self.solde_restant})"


class GroupTontineTransaction(TimestampedModel):
    """Ledger append-only de la cagnotte de la réunion."""

    class TypeOp(models.TextChoices):
        COTISATION = "cotisation", "Cotisation (entrée)"
        VERSEMENT_BENEFICIAIRE = "versement_beneficiaire", "Versement à un bénéficiaire"
        PRET = "pret", "Prêt à un membre (sortie)"
        REMBOURSEMENT_PRET = "remboursement_pret", "Remboursement de prêt (entrée)"
        AJUSTEMENT = "ajustement", "Ajustement"

    group = models.ForeignKey(
        GroupTontine, on_delete=models.PROTECT, related_name="transactions"
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_tontine_transactions",
        help_text="Membre concerné (cotisant, bénéficiaire, emprunteur).",
    )
    loan = models.ForeignKey(
        GroupTontineLoan,
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
        related_name="group_tontine_transactions",
    )
    # Qui a effectué/validé l'action (cotisant, trésorier/président…) — affiché
    # aux membres pour la traçabilité.
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="group_tontine_actions",
    )
    type_op = models.CharField(max_length=24, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    # Solde de la CAGNOTTE de la réunion juste après l'opération.
    solde_apres = money_field()
    date = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Date effective (antidatable). Null → created_at.",
    )
    libelle = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        verbose_name = "Écriture de tontine de groupe"
        verbose_name_plural = "Écritures de tontines de groupe"
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["group", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"

    @property
    def date_effective(self):
        return self.date or self.created_at
