"""Savings domain — one savings account per member with append-only transactions."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from apps_coop.common import TimestampedModel, ZERO, money_field
from apps_coop.members.models import Member


class SavingsAccount(TimestampedModel):
    """Compte de **collecte journalière** (refonte 2026 §4).

    Le nom historique ``SavingsAccount`` est conservé pour ne pas casser les
    20+ références internes (Loan, Payment, WithdrawalRequest, mobile, portail).
    SÉMANTIQUEMENT : c'est le compte de COLLECTE JOURNALIÈRE, pas l'épargne
    classique (qui est ``ClassicSavingsAccount``).

    Règles 2026 :
      - Min 1 000 FCFA/jour (tunable ``collecte.min_per_day``)
      - Multi-jours pré-payé autorisé (5 000 = 5 jours, voir ``nb_jours_couverts``
        sur ``SavingsTransaction`` et ``Payment``)
      - Fin de mois : commission 1% prélevée puis solde restitué en cash OU
        basculé en épargne classique selon ``end_of_month_preference``
      - L'ancien ``taux_interet_applique`` est conservé pour compat legacy mais
        n'est plus utilisé en 2026 (la rémunération a disparu, remplacée par la
        commission inverse).
    """

    class EndOfMonthPreference(models.TextChoices):
        CASH = "cash", "Retrait en cash (à l'agence)"
        MOBILE_MONEY = "mobile_money", "Versement Mobile Money"
        EPARGNE = "epargne", "Bascule vers épargne classique"

    member = models.OneToOneField(
        Member,
        on_delete=models.PROTECT,
        related_name="savings_account",
    )
    solde = money_field(default=ZERO)
    date_ouverture = models.DateField()
    # LEGACY (2025) — taux d'intérêt mensuel ; conservé pour ne pas casser les
    # migrations existantes, ignoré par la logique 2026 (la collecte n'a plus
    # d'intérêt, juste une commission mensuelle).
    taux_interet_applique = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0,
        help_text="LEGACY 2025 — annual rate. Ignoré en 2026 (collecte = commission).",
    )

    # LOT 2 (refonte 2026) — comportement fin de mois.
    end_of_month_preference = models.CharField(
        max_length=16,
        choices=EndOfMonthPreference.choices,
        default=EndOfMonthPreference.CASH,
        help_text=(
            "Choix du membre en fin de mois pour le solde restituable (après "
            "commission) : récupérer en cash à l'agence, se le faire verser en "
            "Mobile Money, ou le basculer vers l'épargne classique."
        ),
    )

    # Destination du versement Mobile Money (préférence ``mobile_money``). Le
    # membre renseigne son numéro + réseau ; le transfert est exécuté
    # manuellement par la coopérative depuis la file de payout admin (sauf si
    # l'automatisation Tara ``collecte.monthly.cash_payout`` est activée).
    payout_phone = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="Numéro Mobile Money de destination (préférence mobile_money).",
    )
    payout_network = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Réseau Mobile Money de destination (MTN, ORANGE…).",
    )

    class Meta:
        verbose_name = "Compte de collecte journalière"
        verbose_name_plural = "Comptes de collecte journalière"

    def __str__(self) -> str:
        return f"Collecte {self.member.numero_membre} · solde={self.solde}"


class SavingsTransaction(TimestampedModel):
    """Append-only ledger des mouvements de COLLECTE JOURNALIÈRE.

    Refonte 2026 : 3 nouveaux ``TypeOp`` posés pour le cron de fin de mois
    (LOT 4 — non implémenté ici, juste les valeurs d'enum disponibles).
    """

    class TypeOp(models.TextChoices):
        DEPOT = "depot", "Dépôt"
        RETRAIT = "retrait", "Retrait"
        INTERET = "interet", "Intérêt"  # LEGACY 2025
        # Prélèvement automatique pour solder un crédit en contentieux (R1).
        RETRAIT_FORCE = "retrait_force", "Prélèvement forcé (crédit en contentieux)"
        # LOT 2 (refonte 2026) — cycle fin de mois.
        COMMISSION = "commission", "Commission mensuelle 1% (refonte 2026)"
        RESTITUTION_CASH = (
            "restitution_cash",
            "Restitution en cash fin de mois (refonte 2026)",
        )
        BASCULE_EPARGNE = (
            "bascule_epargne",
            "Bascule vers épargne classique fin de mois (refonte 2026)",
        )

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
    type_op = models.CharField(max_length=20, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(help_text="Snapshot of account balance immediately after this row.")
    date = models.DateTimeField(db_index=True)
    # LOT 2 (refonte 2026) — multi-jours pré-payé.
    # 1 = versement standard d'1 jour. N > 1 = versement couvrant N jours
    # (ex. 5000 FCFA pour 5 jours à 1000/j). Affiché en historique compact
    # « Versement × N jours ».
    nb_jours_couverts = models.PositiveSmallIntegerField(
        default=1,
        help_text=(
            "Nombre de jours couverts par ce versement (multi-jours pré-payé). "
            "Défaut 1 = versement journalier classique."
        ),
    )
    # L7 (réforme 2026) — Carnet auquel cette écriture est imputée (le plus
    # récent du membre au moment du versement). Null si aucun carnet commandé
    # ou pour les écritures système (commission, restitution…).
    booklet_order = models.ForeignKey(
        "members.BookletOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="collecte_transactions",
        help_text="Carnet le plus récent auquel cette écriture est rattachée.",
    )

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
    """Compte d'**Épargne classique** (refonte 2026 §5).

    Distinct du compte de collecte journalière (``SavingsAccount``). Créé à la
    volée au 1er dépôt.

    Règles 2026 :
      - 0% d'intérêt (rémunération supprimée)
      - Contrat de 12 mois (tunable ``epargne.contract_months``)
      - À maturité : restitution intégrale + frais ré-inscription
        (tunable ``epargne.renewal_fee``)
      - Grace 30 jours après échéance avant archivage
        (tunable ``epargne.renewal_grace_days``)
      - Le membre peut souscrire à la **convention prêteur** (LOT 7) pour
        rendre tout ou partie de son solde disponible au financement crédit.
    """

    class StatutRenouvellement(models.TextChoices):
        ACTIF = "actif", "Actif (loin de l'échéance)"
        NOTIFIE = "notifie", "Rappel d'anniversaire envoyé"
        URGENCE = "urgence", "Échéance imminente"
        EN_ATTENTE_PAIEMENT = (
            "en_attente_paiement",
            "Maturité atteinte, en attente du paiement de re-inscription",
        )
        ARCHIVE = "archive", "Archivé (grace dépassée sans renouvellement)"

    member = models.OneToOneField(
        Member,
        on_delete=models.PROTECT,
        related_name="classic_savings_account",
    )
    solde = money_field(default=ZERO)
    date_ouverture = models.DateField()

    # LOT 2 (refonte 2026) — cycle 1 an + ré-inscription.
    date_prochaine_maturite = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date à laquelle le contrat 12 mois échoit (restitution + frais "
            "ré-inscription). Posée à l'ouverture du compte ou au renouvellement."
        ),
    )
    cycle_courant = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Numéro du cycle annuel en cours. Incrémenté à chaque renouvellement "
            "(restitution + frais payés)."
        ),
    )
    statut_renouvellement = models.CharField(
        max_length=24,
        choices=StatutRenouvellement.choices,
        default=StatutRenouvellement.ACTIF,
        db_index=True,
        help_text="État du cycle de renouvellement annuel.",
    )

    class Meta:
        verbose_name = "Compte épargne classique"
        verbose_name_plural = "Comptes épargne classique"

    def __str__(self) -> str:
        return f"Épargne classique {self.member.numero_membre} · solde={self.solde}"

    # ------------------------------------------------------------------
    # CH-3 — Sous-canal placement (refonte 2026).
    # ------------------------------------------------------------------
    # Le placement réutilise la convention prêteur (LOT 7) : chaque dépôt
    # placement crée une ``LenderTranche`` DISPONIBLE. Le solde "placement
    # actif" = somme des tranches du membre encore DISPONIBLE, GELEE ou
    # ENGAGEE. Le solde librement retirable = solde total − ce montant.
    #
    # GELEE compte comme placement actif : la tranche est immobilisée en
    # garantie d'un crédit, elle n'est plus prêtable mais elle reste bel et
    # bien du placement (l'argent est toujours bloqué côté membre).
    @property
    def solde_placement_actif(self) -> "Decimal":
        """Somme des tranches prêteur du membre encore actives (non restituées)."""
        from decimal import Decimal

        from django.db.models import Sum

        total = (
            LenderTranche.objects.filter(
                member=self.member,
                statut__in=LenderTranche.STATUTS_ACTIFS,
            )
            .aggregate(s=Sum("montant"))["s"]
        )
        return Decimal(total) if total is not None else Decimal("0")

    @property
    def solde_libre(self) -> "Decimal":
        """Part librement retirable = solde total − placements encore actifs."""
        from decimal import Decimal

        return Decimal(self.solde) - self.solde_placement_actif


class ClassicSavingsTransaction(TimestampedModel):
    """Ledger append-only de l'épargne classique.

    Refonte 2026 : 2 nouveaux ``TypeOp`` pour l'anniversaire 1 an.
    """

    class TypeOp(models.TextChoices):
        DEPOT = "depot", "Dépôt"
        RETRAIT = "retrait", "Retrait"
        INTERET = "interet", "Intérêt"  # LEGACY (rare, 0% par défaut)
        # LOT 2 (refonte 2026) — cycle anniversaire.
        RESTITUTION_MATURITE = (
            "restitution_maturite",
            "Restitution intégrale à la maturité 12 mois (refonte 2026)",
        )
        FRAIS_RENOUVELLEMENT = (
            "frais_renouvellement",
            "Frais de ré-inscription annuel (refonte 2026)",
        )
        # LOT 9 (refonte 2026) — Partage 50/50 des intérêts crédit.
        INTERET_PRETEUR = (
            "interet_preteur",
            "Part d'intérêts crédit reversée au prêteur (refonte 2026)",
        )
        # Porte des frais d'étude (2026) — 3e canal de règlement.
        FRAIS_DEMANDE_CREDIT = (
            "frais_demande_credit",
            "Frais d'étude crédit prélevés sur l'épargne (2026)",
        )
        # Intérêts de reconduction réglés « au comptant » par prélèvement.
        INTERETS_RECONDUCTION = (
            "interets_reconduction",
            "Intérêts de reconduction prélevés sur l'épargne",
        )
        # LOT 13 (refonte 2026) — Saisie sur épargne classique (R1 étendue).
        RETRAIT_FORCE = (
            "retrait_force",
            "Prélèvement forcé sur épargne classique (crédit contentieux)",
        )
        # CH-3 (refonte 2026) — Sous-canal placement : intérêt capitalisé à la
        # maturité (12 mois après le dépôt). Une seule ligne par dépôt placement.
        INTERET_PLACEMENT = (
            "interet_placement",
            "Intérêt capitalisé à la maturité d'un dépôt placement (refonte 2026)",
        )
        # Restitution anticipée d'un placement prêteur (apport coop) — LIGNE
        # INFORMATIVE : le capital vivait déjà dans le solde (la tranche n'était
        # qu'un verrou), la restitution le débloque au profit de la part libre.
        # Le solde_apres NE bouge donc PAS pour cette ligne (pas un flux réel) ;
        # elle sert uniquement à rendre la restitution visible sur le relevé.
        RESTITUTION_PLACEMENT = (
            "restitution_placement",
            "Restitution du capital de placement (débloqué au profit de la part libre)",
        )
        # Fin de mois collecte (refonte 2026) — entrée épargne provenant d'une
        # bascule de la collecte (choix membre). Rend le virement identifiable
        # sur le relevé épargne (vs un dépôt MoMo classique).
        BASCULE_COLLECTE = (
            "bascule_collecte",
            "Bascule depuis la collecte (fin de mois)",
        )

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
    type_op = models.CharField(max_length=24, choices=TypeOp.choices, db_index=True)
    montant = money_field()
    solde_apres = money_field(help_text="Solde du compte juste après cette opération.")
    date = models.DateTimeField(db_index=True)

    # L7 (réforme 2026) — Carnet auquel cette écriture est imputée (le plus
    # récent du membre au moment du versement). Null si le membre n'a pas
    # encore commandé de carnet, ou pour les écritures système.
    booklet_order = models.ForeignKey(
        "members.BookletOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="classic_savings_transactions",
        help_text="Carnet le plus récent auquel cette écriture est rattachée.",
    )

    # CH-3 (refonte 2026) — Sous-canal placement.
    is_placement = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "Sous-canal placement (DEPOT) : True = bloqué jusqu'à "
            "`placement_unlock_date`, restitué + intérêt à maturité. "
            "Pour les autres TypeOp ce champ reste False."
        ),
    )
    placement_unlock_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date à partir de laquelle le placement devient libre. Posée par "
            "le hook au dépôt (date_depot + epargne.placement.lock_months). "
            "Null pour tout ce qui n'est pas un DEPOT placement."
        ),
    )

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["account", "-date"])]

    def __str__(self) -> str:
        return f"{self.type_op} {self.montant} → {self.solde_apres}"


class WithdrawalRequest(TimestampedModel):
    """Demande de retrait d'épargne par un membre.

    Le membre choisit son **canal de remise** :
      • ``MOMO`` — payout Mobile Money initié par Tara dès validation admin.
        Champs requis : ``recipient_phone`` + ``network``.
      • ``PRESENTIEL`` — retrait en espèces à l'agence ; l'admin clique
        « Confirmer remise » quand il a remis l'argent.

    Workflow :
        en_attente → approuvee (PRÉSENTIEL — solde débité, attente remise)
                                       → completee (admin marque "remis")
        en_attente → en_payout (MOMO — solde débité, payout Tara en cours)
                                       → completee (webhook Tara confirme)
                                       → payout_failed (Tara KO ; admin réessaye)
        en_attente → rejetee
    """
    from django.conf import settings as _settings

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        APPROUVEE = "approuvee", "Approuvée — remise espèces en attente"
        EN_PAYOUT = "en_payout", "Payout Mobile Money en cours"
        COMPLETEE = "completee", "Complétée (argent remis)"
        PAYOUT_FAILED = "payout_failed", "Payout Mobile Money échoué"
        REJETEE = "rejetee", "Rejetée"

    class ModePaiement(models.TextChoices):
        MOMO = "momo", "Mobile Money (payout Tara)"
        PRESENTIEL = "presentiel", "Espèces à l'agence"

    class Network(models.TextChoices):
        MTN = "MTN", "MTN Mobile Money"
        ORANGE = "ORANGE", "Orange Money"
        WAVE = "WAVE", "Wave"
        AIRTEL = "AIRTEL", "Airtel Money"

    class Source(models.TextChoices):
        """Produit d'épargne d'où provient l'argent retiré.

        • ``COLLECTE`` — compte de collecte journalière (``SavingsAccount``).
          Comportement historique, débit sur ``account.solde``.
        • ``CLASSIQUE_LIBRE`` — part **librement retirable** de l'épargne
          classique (``ClassicSavingsAccount.solde_libre`` = solde total −
          placements encore actifs). Le placement reste bloqué jusqu'à
          maturité (il garantit les engagements crédit), donc un retrait
          classique ne peut jamais entamer ``solde_placement_actif``.
        """
        COLLECTE = "collecte", "Collecte journalière"
        CLASSIQUE_LIBRE = "classique_libre", "Épargne classique (part libre)"

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.COLLECTE,
        db_index=True,
        help_text="Produit d'épargne d'où provient le retrait.",
    )
    # COLLECTE → ``account`` renseigné ; CLASSIQUE_LIBRE → ``classic_account``
    # renseigné. Les deux FK sont nullable : exactement une des deux est posée
    # selon ``source`` (invariant garanti par le service ``request_withdrawal``).
    account = models.ForeignKey(
        SavingsAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="withdrawal_requests",
    )
    classic_account = models.ForeignKey(
        "savings.ClassicSavingsAccount",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="withdrawal_requests",
    )
    montant = money_field()
    # Frais de transaction (%) prélevé EN PLUS, au paiement (règle 2026-08-11) :
    # l'épargne est débitée de `montant + frais_transaction`, le membre reçoit
    # `montant`, la coopérative encaisse `frais_transaction`. 0 par défaut
    # (dépend du taux TRANSACTION_FEE + du périmètre payments.transaction_fee.operations).
    frais_transaction = money_field(default=0)
    motif = models.TextField(blank=True, help_text="Raison du retrait (renseignée par le membre).")

    # --- Canal de remise (refonte 2026 — choisi par le membre) ----------
    mode_paiement = models.CharField(
        max_length=12,
        choices=ModePaiement.choices,
        default=ModePaiement.PRESENTIEL,
        help_text="Canal choisi par le membre pour récupérer son argent.",
    )
    recipient_phone = models.CharField(
        max_length=32,
        blank=True,
        help_text="Numéro MOMO/OM où envoyer l'argent (mode MOMO uniquement).",
    )
    network = models.CharField(
        max_length=16,
        choices=Network.choices,
        blank=True,
        help_text="Réseau Mobile Money (mode MOMO uniquement).",
    )

    statut = models.CharField(
        max_length=16,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
        db_index=True,
    )
    motif_rejet = models.TextField(blank=True)

    # Transaction de débit créée à l'approbation (trace le mouvement de solde).
    # COLLECTE → ``transaction`` (SavingsTransaction). CLASSIQUE_LIBRE →
    # ``classic_transaction`` (ClassicSavingsTransaction).
    transaction = models.OneToOneField(
        "savings.SavingsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_request",
    )
    classic_transaction = models.OneToOneField(
        "savings.ClassicSavingsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_request",
    )
    # Payment de décaissement créé lors d'un payout MOMO (lié au webhook Tara).
    payout_payment = models.OneToOneField(
        "payments.Payment",
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
    # Agent qui a marqué la remise espèces (PRÉSENTIEL).
    handed_over_by = models.ForeignKey(
        _settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_handovers",
    )
    handed_over_at = models.DateTimeField(null=True, blank=True)

    date_demande = models.DateTimeField(auto_now_add=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "Demande de retrait"
        verbose_name_plural = "Demandes de retrait"
        indexes = [models.Index(fields=["statut", "-date_demande"])]

    @property
    def member(self) -> Member:
        """Membre propriétaire du retrait, quelle que soit la source.

        Résout depuis ``account`` (collecte) ou ``classic_account`` (classique)
        selon ce qui est renseigné. Évite les ``wr.account.member`` qui
        planteraient sur un retrait classique (``account`` null).
        """
        if self.account_id:
            return self.account.member
        return self.classic_account.member

    def __str__(self) -> str:
        try:
            numero = self.member.numero_membre
        except (SavingsAccount.DoesNotExist, AttributeError):  # pragma: no cover
            numero = "?"
        return f"Retrait {self.montant} · {numero} · {self.source} · {self.statut}"


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 7 : Épargne-prêteur (§6 BUSINESS_RULES_2026)
# ---------------------------------------------------------------------------
#
# Un membre peut **opter** pour rendre son épargne classique disponible au
# financement des crédits d'autres membres. En échange il touche ½ des intérêts
# (LOT 9) et accepte le risque (s'il n'est jamais saisi en contentieux).
#
# Deux modes combinables :
#  • Mode A — Global   → ``LenderConsent.is_global=True`` : tout le solde
#                       épargne est prêtable, ajusté dynamiquement.
#  • Mode B — Tranches → plusieurs ``LenderTranche`` à montant fixe, chacune
#                       passe de ``DISPONIBLE`` → ``ENGAGEE`` quand un crédit
#                       la consomme (LOT 8 funding).


class LenderConsent(TimestampedModel):
    """Opt-in d'un membre à la **convention prêteur** (§6 BUSINESS_RULES_2026).

    1 consentement = 1 membre. Création = signature de la convention papier
    scannée, posée dans ``convention_document``. Tant que ``revoked_at`` est
    nul, le membre est considéré "prêteur actif".

    Révocation : possible uniquement si **aucune** ``LenderTranche`` n'est en
    statut ``ENGAGEE`` (un crédit ne peut pas être démuni de son funding
    pendant qu'il vit). Sinon ``revoke_consent`` lève ``ValueError``.
    """

    member = models.OneToOneField(
        Member,
        on_delete=models.PROTECT,
        related_name="lender_consent",
    )
    is_global = models.BooleanField(
        default=False,
        help_text=(
            "Mode A : True = tout le solde épargne classique est prêtable. "
            "False = mode B (tranches explicites uniquement)."
        ),
    )
    convention_signed_at = models.DateTimeField(
        help_text="Date de signature de la convention prêteur."
    )
    convention_document = models.FileField(
        upload_to="coop/conventions_preteur/%Y/%m/",
        null=True,
        blank=True,
        help_text="Scan PDF / image de la convention signée.",
    )
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Date de révocation du consentement. Tant qu'il est nul, le membre "
            "est considéré comme prêteur actif. Révocation impossible si une "
            "tranche est encore engagée dans un crédit."
        ),
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lender_consents_revoked",
    )

    class Meta:
        verbose_name = "Convention prêteur"
        verbose_name_plural = "Conventions prêteur"
        indexes = [models.Index(fields=["revoked_at"])]

    def __str__(self) -> str:
        state = "révoquée" if self.revoked_at else "active"
        mode = "global" if self.is_global else "tranches"
        return f"Consent {self.member.numero_membre} · {mode} · {state}"

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class LenderTranche(TimestampedModel):
    """Tranche d'épargne explicitement mise à disposition pour le funding crédit.

    En mode B (``LenderConsent.is_global=False``) le membre crée une ou
    plusieurs tranches actives ; chacune représente un montant figé qu'il
    accepte de bloquer à des fins de prêt.

    En mode A (global) le membre peut quand même créer des tranches mais
    ``capacite_pretable`` s'en moque : il déduit ``solde - tranches_engagees``
    directement. Les tranches en mode A ne servent qu'à tracer le funding.

    Cycle de vie : ``DISPONIBLE`` → ``ENGAGEE`` (au moment du funding d'un
    crédit, LOT 8) → ``LIBEREE`` (à la clôture du crédit, intégralité
    remboursée) ou ``ANNULEE`` (membre annule avant engagement).

    Réforme garantie 2026 : branche parallèle ``DISPONIBLE`` → ``GELEE`` quand
    la tranche est immobilisée en garantie d'un crédit (collatéral demandeur ou
    caution avaliste), puis retour ``GELEE`` → ``DISPONIBLE`` au rejet de la
    demande ou à la clôture du crédit garanti. Une tranche GELEE **sort du pool
    prêteur** : le même argent ne peut pas garantir un crédit et en financer un
    autre.
    """

    class Statut(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible (libre d'engagement)"
        GELEE = "gelee", "Gelée en garantie d'un crédit"
        ENGAGEE = "engagee", "Engagée dans un crédit"
        LIBEREE = "liberee", "Libérée (crédit clôturé)"
        ANNULEE = "annulee", "Annulée par le membre"

    #: Statuts où l'argent de la tranche est encore immobilisé côté membre
    #: (donc non retirable). Exclut LIBEREE / ANNULEE, qui rendent la main.
    STATUTS_ACTIFS = (
        Statut.DISPONIBLE,
        Statut.GELEE,
        Statut.ENGAGEE,
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="lender_tranches",
    )
    montant = money_field(help_text="Montant alloué à cette tranche, en XAF.")
    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.DISPONIBLE,
        db_index=True,
    )
    # FK string-style — Loan vit dans apps_coop.loans, évite le cycle d'import.
    engaged_in_loan = models.ForeignKey(
        "loans.Loan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="engaged_tranches",
        help_text="Crédit qui consomme cette tranche (posé au passage ENGAGEE).",
    )
    engaged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Horodatage du passage DISPONIBLE → ENGAGEE.",
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Horodatage du passage ENGAGEE → LIBEREE (crédit clôturé).",
    )
    #: Écriture d'épargne placement qui a créé cette tranche (dépôt placement).
    #: Permet de contre-passer proprement la tranche si le paiement source est
    #: invalidé par l'admin (sinon la tranche DISPONIBLE restait orpheline =
    #: argent fantôme mobilisable en funding).
    source_transaction = models.ForeignKey(
        "ClassicSavingsTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lender_tranches",
        help_text="Dépôt placement à l'origine de la tranche (traçabilité invalidation).",
    )
    # Réforme garantie 2026 — immobilisation en garantie.
    gele_par_loan_request = models.ForeignKey(
        "loans.LoanRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tranches_gelees",
        help_text=(
            "Demande de crédit dont la garantie immobilise cette tranche "
            "(posé au passage DISPONIBLE → GELEE)."
        ),
    )
    gele_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Horodatage du passage DISPONIBLE → GELEE.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Tranche prêteur"
        verbose_name_plural = "Tranches prêteur"
        indexes = [
            models.Index(fields=["member", "statut"]),
            models.Index(fields=["statut", "-created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"Tranche {self.member.numero_membre} · "
            f"{self.montant} XAF · {self.statut}"
        )
