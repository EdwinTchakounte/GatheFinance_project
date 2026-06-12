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


class MicrocreditCampaign(TimestampedModel):
    """Campagne micro-crédit pour nouveaux adhérents (refonte 2026 §8 / LOT 11).

    Voie 3 d'éligibilité : un non-adhérent peut emprunter dans la fenêtre
    [date_debut, date_fin] d'une campagne active. Pas d'épargne ni d'avaliste
    exigés — la coop assume seule le risque. Le bénéficiaire est créé avec
    ``Member.statut = TEMPORAIRE`` et peut basculer ``ADHERENT`` en payant
    les frais d'inscription après remboursement (Q15).
    """

    nom = models.CharField(
        max_length=120,
        help_text='Libellé interne, ex. "Campagne commerçants Q3 2026".',
    )
    profil_cible = models.CharField(
        max_length=64,
        help_text='Profil ciblé (libre), ex. "commercants", "parents", "agriculteurs".',
    )
    date_debut = models.DateField(
        db_index=True,
        help_text="Premier jour d'ouverture de la campagne (inclus).",
    )
    date_fin = models.DateField(
        db_index=True,
        help_text="Dernier jour d'ouverture (inclus). Au-delà, le cron pose actif=False.",
    )

    montant_min = money_field(
        default=ZERO,
        help_text="Plancher de montant (FCFA). 0 = pas de plancher.",
    )
    montant_max = money_field(
        help_text="Plafond de montant (FCFA), ex. 50 000.",
    )
    taux_interet = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        help_text="Taux flat appliqué à la création du Loan, ex. 0.10 (10 %).",
    )
    nb_jours_recouvrement = models.PositiveIntegerField(
        help_text="Durée du recouvrement par collectes journalières dédiées, ex. 60.",
    )
    plafond_beneficiaires = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Nombre maximum de bénéficiaires acceptés (None = pas de plafond). "
            "Bloque les nouvelles demandes une fois atteint."
        ),
    )

    actif = models.BooleanField(
        default=True,
        db_index=True,
        help_text=(
            "Toggle admin. La campagne n'accepte des demandes QUE si actif=True "
            "ET aujourd'hui ∈ [date_debut, date_fin]. Posé False par le cron "
            "``close_expired_campaigns`` après date_fin."
        ),
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date à laquelle la campagne a été clôturée (cron ou admin).",
    )
    close_reason = models.CharField(
        max_length=64,
        blank=True,
        help_text='Motif de clôture, ex. "expired", "manual", "quota_reached".',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="microcampaigns_created",
        help_text="Admin auteur de la campagne (audit).",
    )

    # Communication — flyer affiché côté admin et notifié aux membres ciblés.
    flyer = models.ImageField(
        upload_to="coop/microcampaigns/flyers/%Y/%m/",
        null=True,
        blank=True,
        help_text="Visuel attaché à la campagne (PNG/JPG) — affiché aux membres ciblés.",
    )

    # Audience — membres explicitement ciblés par la campagne (notification, segmentation).
    # Indépendant de ``beneficiaires`` qui ne se matérialise qu'au moment où un
    # Member TEMPORAIRE est créé via une demande de crédit acceptée. Un membre
    # peut être ciblé sans avoir encore demandé.
    targeted_members = models.ManyToManyField(
        "members.Member",
        related_name="targeted_campaigns",
        blank=True,
        help_text="Membres explicitement ciblés (notification + segmentation manuelle admin).",
    )

    class Meta:
        ordering = ["-date_debut", "-id"]
        verbose_name = "Campagne micro-crédit"
        verbose_name_plural = "Campagnes micro-crédit"
        indexes = [
            models.Index(fields=["actif", "-date_debut"]),
            models.Index(fields=["actif", "date_fin"]),
        ]

    def __str__(self) -> str:
        return f"{self.nom} · {self.date_debut} → {self.date_fin}"


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
        # CH-6 — Double approbation (provisoire → visite terrain → définitive).
        # APPROUVEE_PROVISOIRE = décision provisoire favorable du comité, sous
        # réserve d'une visite terrain. Avant le passage à APPROUVEE.
        APPROUVEE_PROVISOIRE = (
            "approuvee_provisoire",
            "Approuvée provisoirement (visite terrain à effectuer)",
        )
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"
        # Refonte 2026 (LOT 10) — Voie 2 AVALISTE (§7.2 BUSINESS_RULES_2026).
        EN_ATTENTE_AVALISTE = (
            "en_attente_avaliste",
            "En attente de l'acceptation de l'avaliste",
        )
        REJETEE_AVALISTE = (
            "rejetee_avaliste",
            "Refusée par l'avaliste (terminal)",
        )
        # Refonte 2026 (LOT 11) — Voie 3 MICROCAMPAIGN (§8 BUSINESS_RULES_2026).
        EN_VALIDATION_CAMPAGNE = (
            "en_validation_campagne",
            "Micro-crédit campagne — en validation activité",
        )
        REJETEE_CAMPAGNE = (
            "rejetee_campagne",
            "Refusée — micro-crédit campagne (terminal)",
        )

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

    # CH-4 — Champs additionnels FormSchema (loan_request).
    extra_payload = models.JSONField(
        default=dict, blank=True,
        help_text="Champs FormSchema additionnels (id_champ → valeur).",
    )
    form_schema_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Version du FormSchema 'loan_request' actif lors de la soumission.",
    )

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

    # CH-6 — Visite terrain entre approbation provisoire et décision définitive.
    # L'agent terrain est différent du président comité ; il remplit un rapport
    # qui conditionne la validation définitive.
    field_visit_done_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Date à laquelle la visite terrain a été effectuée.",
    )
    field_visit_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="loan_requests_visited",
        help_text="Agent qui a effectué la visite terrain.",
    )
    field_visit_outcome = models.CharField(
        max_length=16, blank=True,
        choices=[
            ("favorable", "Favorable — peut être approuvée définitivement"),
            ("defavorable", "Défavorable — propose le rejet"),
            ("a_revoir", "À revoir — informations à compléter"),
        ],
        help_text="Recommandation de l'agent terrain au comité.",
    )
    field_visit_note = models.TextField(
        blank=True,
        help_text="Compte-rendu de la visite (observations sur le demandeur, l'activité, le local).",
    )

    # Refonte 2026 (LOT 10) — Voie d'éligibilité AVALISTE.
    # Posé une fois l'``AvalisteConsent`` accepté par l'avaliste. Indispensable
    # pour les écritures de phase contentieux (R1 + R2 saisissent les deux
    # comptes, cf. §9 et LOT 13 BUSINESS_RULES_2026).
    avaliste = models.ForeignKey(
        "members.Member",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loan_requests_avalisee",
        help_text=(
            "Ancien qui se porte garant. Posé après ``AvalisteConsent.statut "
            "= ACCEPTED``. NULL pour les voies SENIOR_BRC et CAMPAIGN."
        ),
    )

    # Refonte 2026 (LOT 11) — Voie 3 MICROCAMPAIGN.
    # Posé à la soumission d'une demande dans le cadre d'une campagne active.
    # ``avaliste`` reste NULL, ``microcampaign`` est non-NULL — exclusif des
    # deux autres voies. Le Member est créé en ``TEMPORAIRE`` (Q15).
    microcampaign = models.ForeignKey(
        "loans.MicrocreditCampaign",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loan_requests",
        help_text=(
            "Campagne micro-crédit d'origine. NULL pour les voies SENIOR_BRC "
            "et AVALISTE. Posé à la soumission via ``submit_microcampaign_request``."
        ),
    )

    # CH-9 — Moyen de réception choisi par le membre à la soumission.
    # Saisi en amont (avant approbation), il pilote ensuite l'auto-fill du
    # payout Tara et apparaît sur la note de demande PDF (Sinora §5.3 flow).
    class MoyenReception(models.TextChoices):
        TARA_OM = "tara_om", "Tara Orange Money"
        TARA_MOMO = "tara_momo", "Tara MTN MoMo"
        AGENCE_ESPECES = "agence_especes", "Retrait espèces en agence"

    moyen_reception = models.CharField(
        max_length=16,
        choices=MoyenReception.choices,
        blank=True,
        help_text=(
            "Canal choisi par le membre pour recevoir le décaissement. "
            "Pilote l'auto-fill du payout Tara à la mise à disposition."
        ),
    )
    recipient_phone = models.CharField(
        max_length=32,
        blank=True,
        help_text=(
            "Numéro Mobile Money du membre — requis si moyen_reception "
            "= tara_om ou tara_momo. Vide pour agence_especes."
        ),
    )

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
            "Par défaut 0.1000 (= 10 % par transaction). FIGÉ au décaissement — "
            "un changement de taux global n'affecte que les futurs crédits."
        ),
    )
    # EXT-versioning : taux de pénalité **figé** au décaissement (juridiquement,
    # le membre signe un contrat avec un taux donné — un changement admin
    # ultérieur ne doit pas s'appliquer rétroactivement). NULL = legacy
    # (avant la migration EXT-versioning) → fallback sur ``get_rate`` au calcul.
    taux_penalite = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Taux de pénalité (Article 12) figé au décaissement. Par défaut "
            "0.5000 (= 50 %). NULL = crédit antérieur à EXT-versioning."
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

    # CH-8 — Date butoire formelle (échéancier souple, date butoire stricte).
    # Posée à la création du Loan = date_premiere_echeance + duree_mois.
    # Modifiable par l'admin (extension exceptionnelle à la demande du membre).
    # Dépasser cette date sans solde nul = déclenchement pénalité globale +
    # passage en contentieux.
    date_butoire = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Date butoire formelle pour solder le crédit. Les échéances "
            "individuelles sont indicatives ; seule la date butoire engage. "
            "Modifiable par l'admin via /extend-deadline/ avec audit."
        ),
    )

    montant_total_du = money_field(help_text="Principal + total interests over full term.")
    solde_restant = money_field()

    # CH-11 — Retenue des intérêts à la source (Sinora §5.3).
    # Quand ``mode_retenue_interets = "source"`` (réglage 2026-06-12) :
    #   * Le membre demande 100 000, ``montant`` = 100 000 (nominal).
    #   * ``interets_retenus_source`` = 10 000 (= montant × taux_interet).
    #   * ``montant_decaisse_net`` = 90 000 (ce qu'il reçoit en main).
    #   * ``montant_total_du`` = 90 000 (capital pur — il rembourse uniquement
    #     ce qu'il a touché). L'échéancier ne contient plus d'intérêts.
    # Pour les crédits historiques antérieurs à CH-11 (mode "echeances") :
    #   * ``interets_retenus_source`` = 0, ``montant_decaisse_net`` = ``montant``.
    #   * Échéancier inchangé (capital + intérêts répartis).
    class ModeRetenue(models.TextChoices):
        ECHEANCES = "echeances", "Intérêts répartis sur les échéances (legacy)"
        SOURCE = "source", "Intérêts retenus à la source à la mise à disposition"

    mode_retenue_interets = models.CharField(
        max_length=12,
        choices=ModeRetenue.choices,
        default=ModeRetenue.ECHEANCES,
        help_text=(
            "Mode de paiement des intérêts. 'source' = retenus à la mise à "
            "disposition (CH-11), 'echeances' = répartis sur les remboursements "
            "(comportement historique)."
        ),
    )
    montant_decaisse_net = money_field(
        null=True,
        blank=True,
        help_text=(
            "Montant réellement versé au membre au décaissement. En mode "
            "'source' = montant - interets_retenus_source. En mode 'echeances' "
            "= montant. NULL = legacy pre-CH-11."
        ),
    )
    interets_retenus_source = money_field(
        null=True,
        blank=True,
        help_text=(
            "Intérêts ponctionnés par la coop à la mise à disposition. En "
            "mode 'source' = montant × taux_interet. En mode 'echeances' = 0. "
            "NULL = legacy pre-CH-11."
        ),
    )

    # CH-12 — Snapshot du taux de partage prêteurs / coop figé à l'approbation
    # du Loan. La valeur courante vit dans l'AppSetting ``lender.interest_share_rate``
    # (modifiable côté admin) ; on la FIGE ici pour éviter qu'un changement
    # ultérieur ne s'applique rétroactivement à un crédit déjà décaissé.
    interest_share_rate_fige = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=(
            "Taux de partage des intérêts prêteurs vs coop, figé à "
            "l'approbation (CH-12). Ex. 0.5000 = 50 % aux prêteurs, 50 % à "
            "la coop. NULL = legacy ou pas de prêteurs."
        ),
    )

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

    # ──────────────────────────────────────────────────────────────────────
    # Cycle contentieux (nouvelle règle) — pénalité globale au franchissement
    # de la date limite + prélèvement automatique épargne après 30 j.
    # ──────────────────────────────────────────────────────────────────────

    # Pénalité GLOBALE — 50 % × solde_restant, appliquée 1 seule fois quand la
    # date limite globale du crédit (= dernière échéance) est franchie sans
    # remboursement complet. Remplace la pénalité par échéance Art.12 dès que
    # ``loans.penalite_par_echeance.enabled=false`` (défaut).
    penalite_globale_appliquee_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'application de la pénalité globale 50 % × solde_restant.",
    )
    penalite_globale_montant = money_field(
        null=True,
        blank=True,
        help_text="Montant de la pénalité globale ajoutée au solde restant.",
    )

    # Passage en contentieux — déclenché par le cron N jours après l'application
    # de la pénalité globale (N = ``loans.penalite_globale.grace_days``, défaut 30).
    contentieux_declenche_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de bascule en CONTENTIEUX (déclenche la saisie épargne).",
    )

    # Saisie automatique épargne (R1) — opérée par le cron au passage en
    # contentieux. ``epargne_saisie_montant`` peut être inférieur au solde
    # restant si l'épargne du membre ne couvre pas tout.
    epargne_saisie_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date du prélèvement forcé sur l'épargne du membre.",
    )
    epargne_saisie_montant = money_field(
        null=True,
        blank=True,
        help_text="Montant effectivement prélevé sur l'épargne (≤ solde_restant).",
    )

    # Poursuites judiciaires — flag posé automatiquement quand le prélèvement
    # épargne n'a pas couvert l'intégralité de la dette. Pas de logique
    # automatique au-delà : c'est un acte humain (huissier, avocat).
    poursuite_judiciaire_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date d'engagement des poursuites (épargne insuffisante).",
    )

    class Meta:
        ordering = ["-date_decaissement"]
        indexes = [models.Index(fields=["member", "statut"])]

    def __str__(self) -> str:
        return f"{self.numero_dossier} · {self.member.numero_membre} · {self.statut}"

    @property
    def date_limite_globale(self):
        """Date limite globale du crédit.

        CH-8 — Préfère ``date_butoire`` (champ formel modifiable) si posée,
        sinon fallback sur la date de la dernière échéance (legacy).

        Sert de borne pour le cycle contentieux : c'est la date à partir de
        laquelle la pénalité globale (50 % × solde_restant) s'applique si
        ``solde_restant > 0``. Retourne ``None`` si aucune échéance n'a été
        générée (cas pathologique).
        """
        if self.date_butoire is not None:
            return self.date_butoire
        last = (
            self.installments.order_by("-date_echeance")
            .values_list("date_echeance", flat=True)
            .first()
        )
        return last


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
    # Refonte 2026 (LOT 9) — Cumul de la part *intérêt* déjà imputée sur cette
    # échéance, calculée à chaque ``LoanRepayment`` (priorité intérêt avant
    # capital). Sert au calcul du partage 50/50 des intérêts : on retire la
    # portion intérêt de l'imputation courante puis on la répartit entre la
    # coop et les ``LenderAllocation`` du crédit.
    interets_payes = money_field(default=ZERO)
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

    # CH-4 — Champs additionnels FormSchema (loan_renewal).
    extra_payload = models.JSONField(
        default=dict, blank=True,
        help_text="Champs FormSchema additionnels (id_champ → valeur).",
    )
    form_schema_version = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Version du FormSchema 'loan_renewal' actif lors de la soumission.",
    )

    class Meta:
        ordering = ["-date_demande"]
        verbose_name = "Reconduction"
        verbose_name_plural = "Reconductions"

    def __str__(self) -> str:
        return f"Reconduction {self.loan.numero_dossier} · {self.statut}"


# ---------------------------------------------------------------------------
# EXT-2 — Tables de configuration : paliers Art.7 + modalités Art.8
# ---------------------------------------------------------------------------
#
# Le défaut réglementaire vit dans ``loans/terms.py`` (LOAN_DURATION_TIERS /
# PaymentModality.INSTALLMENTS_PER_MONTH) et sert de fallback si la table
# DB est vide / non migrée. ``terms.duration_months_for`` et
# ``terms.n_installments`` lisent ces tables en priorité.


class LoanDurationTier(TimestampedModel):
    """Palier (montant → durée) du Règlement Article 7, modifiable par l'admin.

    Le palier est inclusif sur ``montant_min`` et ``montant_max``. Laisser
    ``montant_max`` à ``NULL`` signifie « pas de borne haute » (dernier
    palier). Seules les lignes ``actif=True`` sont prises en compte.
    """

    montant_min = money_field()
    montant_max = money_field(null=True, blank=True)
    duree_mois = models.PositiveSmallIntegerField(
        help_text="Nombre de mois de remboursement pour ce palier.",
    )
    actif = models.BooleanField(default=True, db_index=True)
    ordering = models.PositiveSmallIntegerField(
        default=100,
        help_text="Ordre d'évaluation (plus bas = plus tôt). Utile uniquement "
        "si plusieurs paliers se chevauchent — sinon laisser 100.",
    )

    class Meta:
        ordering = ["ordering", "montant_min"]
        verbose_name = "Palier de durée (Art. 7)"
        verbose_name_plural = "Paliers de durée (Art. 7)"

    def __str__(self) -> str:
        hi = f"{self.montant_max}" if self.montant_max is not None else "∞"
        return f"[{self.montant_min} – {hi}] → {self.duree_mois} mois"


class PaymentModalityConfig(TimestampedModel):
    """Modalité de remboursement (Article 8), modifiable par l'admin.

    Les 3 modalités réglementaires sont seedées par défaut. L'admin peut
    désactiver une modalité (``actif=False``) ou ajuster
    ``installments_per_month`` si la coop revoit son calendrier (rare).
    """

    code = models.CharField(max_length=16, unique=True, db_index=True)
    libelle = models.CharField(max_length=64)
    installments_per_month = models.PositiveSmallIntegerField(
        help_text="Nombre d'échéances par mois pour cette cadence (ex. 30 "
        "pour journalier, 4 pour hebdo, 1 pour mensuel).",
    )
    actif = models.BooleanField(default=True, db_index=True)
    ordering = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["ordering", "code"]
        verbose_name = "Modalité de paiement (Art. 8)"
        verbose_name_plural = "Modalités de paiement (Art. 8)"

    def __str__(self) -> str:
        return f"{self.libelle} ({self.installments_per_month}/mois)"


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 7 : Épargne-prêteur (§6 BUSINESS_RULES_2026)
# ---------------------------------------------------------------------------
#
# ``LenderConsent`` / ``LenderTranche`` vivent dans ``apps_coop.savings`` (côté
# membre épargnant). Ici on pose la trace **côté crédit** : pour un Loan donné,
# quel(s) prêteur(s) ont financé quelle quote-part. Sert au :
#   • décaissement (savoir d'où vient l'argent)
#   • split 50/50 des intérêts (LOT 9 — qui touche combien à chaque échéance)
#   • R1 / contentieux (LOT 13 — savoir QUI exclure de la saisie : les
#     tranches engagées d'un prêteur ne lui sont pas saisies)


class LenderAllocation(TimestampedModel):
    """Allocation d'une portion d'un Loan à un prêteur (refonte 2026 §6).

    Pour un ``Loan`` donné on a 1..N ``LenderAllocation`` : chacune dit
    « tel membre prêteur a financé ``montant_alloue`` du crédit, soit
    ``quote_part`` % du total ». La somme des ``montant_alloue`` de toutes
    les allocations d'un Loan doit égaler ``Loan.montant`` (vérifié par le
    service de finalisation funding, LOT 8).

    ``quote_part`` est figée au moment de la finalisation funding et sert
    de base au calcul de la part d'intérêts à reverser au prêteur à chaque
    remboursement d'échéance (LOT 9).
    """

    loan = models.ForeignKey(
        Loan,
        on_delete=models.PROTECT,
        related_name="lender_allocations",
    )
    lender = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="lender_allocations",
        help_text="Le membre prêteur qui finance cette quote-part du crédit.",
    )
    tranche = models.ForeignKey(
        "savings.LenderTranche",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="allocations",
        help_text=(
            "Tranche explicite consommée (mode B). Null si le funding utilise "
            "directement le solde global du prêteur (mode A)."
        ),
    )
    montant_alloue = money_field(help_text="Montant en XAF financé par ce prêteur.")
    quote_part = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        help_text=(
            "Ratio (0.00000001 — 1.0) figé au funding ; détermine la fraction "
            "des intérêts à reverser au prêteur (LOT 9). Toujours égal à "
            "``montant_alloue / Loan.montant`` mais stocké pour éviter les "
            "arrondis successifs."
        ),
    )
    interest_share_paid_total = money_field(
        default=ZERO,
        help_text="Cumul des intérêts déjà versés à ce prêteur sur ce crédit.",
    )

    class Meta:
        ordering = ["loan", "-created_at"]
        verbose_name = "Allocation prêteur"
        verbose_name_plural = "Allocations prêteur"
        indexes = [
            models.Index(fields=["loan", "lender"]),
            models.Index(fields=["lender", "-created_at"]),
        ]
        constraints = [
            # Un même prêteur peut financer plusieurs tranches d'un même crédit
            # SI elles passent par des LenderTranche distinctes. Garantir
            # qu'on ne double pas la même tranche sur le même crédit.
            models.UniqueConstraint(
                fields=["loan", "tranche"],
                condition=models.Q(tranche__isnull=False),
                name="lender_allocation_unique_tranche_per_loan",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Alloc {self.lender.numero_membre} → {self.loan.numero_dossier} · "
            f"{self.montant_alloue} XAF ({float(self.quote_part) * 100:.2f}%)"
        )


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 8 : Funding state machine 24h (§7.3 BUSINESS_RULES_2026)
# ---------------------------------------------------------------------------
#
# Une fois la demande de crédit approuvée par le comité (LOT 12 / voie SENIOR
# ou AVALISTE), le système cherche du financement chez les épargneurs-prêteurs.
# Flow :
#   1. ``request_funding(loan)`` crée 1 ``LoanFundingRequest`` + N ``LenderConsentRequest``
#      (1 par prêteur sollicité). Notif PARALLÈLE aux N prêteurs (LOT 9).
#   2. Chaque prêteur a 24h pour répondre. Silence = acceptation tacite.
#   3. Cron ``loans.funding_window_expiry`` (toutes les ~15min) finalise :
#      • Tous acceptés (explicite ou tacite) → ``FUNDED`` + ``LenderAllocation`` posées
#      • Au moins 1 refus → tente une réallocation (vague suivante)
#      • Réallocation impossible → ``EN_ATTENTE_FUNDING`` (intervention admin)


class LoanFundingRequest(TimestampedModel):
    """Demande de financement d'un Loan par les épargneurs-prêteurs.

    1 demande par Loan (``OneToOneField``). Sert d'agrégat pour les N
    ``LenderConsentRequest`` envoyés aux prêteurs sélectionnés.

    State machine :

        PENDING ──────► ALL_ACCEPTED ──► FUNDED
           │                                ▲
           │ (≥1 refus)                     │ (finalisé : allocations posées,
           │                                │ tranches → ENGAGEE)
           ▼                                │
        REALLOCATING ───► (succès) ─────────┘
           │
           │ (échec — pas de prêteur dispo)
           ▼
        EN_ATTENTE_FUNDING ──► (admin trigger / annulation) ──► CANCELLED
    """

    class Statut(models.TextChoices):
        PENDING = "pending", "En attente de réponse (fenêtre 24h)"
        ALL_ACCEPTED = "all_accepted", "Tous accepté (ou silence tacite)"
        REALLOCATING = "reallocating", "Réallocation en cours (un refus)"
        EN_ATTENTE_FUNDING = "en_attente_funding", "En attente — funding impossible"
        FUNDED = "funded", "Financé (allocations posées)"
        CANCELLED = "cancelled", "Annulé (intervention admin)"

    class Strategy(models.TextChoices):
        FIRST_FIT = "first_fit", "First-fit (prêteurs avec plus de capacité d'abord)"
        BALANCED = "balanced", "Balanced (réparti équitablement)"

    loan = models.OneToOneField(
        Loan,
        on_delete=models.PROTECT,
        related_name="funding_request",
    )
    montant_total = money_field(
        help_text="Montant à financer (= Loan.montant, copié pour traçabilité)."
    )
    statut = models.CharField(
        max_length=24,
        choices=Statut.choices,
        default=Statut.PENDING,
        db_index=True,
    )
    strategy = models.CharField(
        max_length=12,
        choices=Strategy.choices,
        default=Strategy.FIRST_FIT,
        help_text="Algorithme d'allocation utilisé. Tunable globalement via AppSetting.",
    )
    deadline = models.DateTimeField(
        db_index=True,
        help_text=(
            "Date butoir de la vague courante (= created_at + funding.window_hours). "
            "Réinitialisée à chaque réallocation."
        ),
    )
    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de finalisation (passage à FUNDED ou EN_ATTENTE_FUNDING).",
    )
    wave_number = models.PositiveSmallIntegerField(
        default=1,
        help_text="Numéro de vague (incrementé à chaque réallocation). 1 = vague initiale.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande de financement crédit"
        verbose_name_plural = "Demandes de financement crédit"
        indexes = [
            models.Index(fields=["statut", "deadline"]),
        ]

    def __str__(self) -> str:
        return (
            f"Funding {self.loan.numero_dossier} · {self.montant_total} XAF · "
            f"v{self.wave_number} · {self.statut}"
        )


class LenderConsentRequest(TimestampedModel):
    """Demande de consentement envoyée à UN prêteur pour UNE proposition.

    1 ligne par prêteur sollicité par vague. La réponse est :
      • ACCEPTED (réponse explicite OK)
      • AUTO_ACCEPTED (silence à l'expiration du délai, traité comme accepté)
      • REFUSED (réponse explicite refus)
      • OBSOLETE (remplacée par une vague suivante après réallocation)

    En mode B, ``tranche`` pointe vers la ``LenderTranche`` DISPONIBLE qui sera
    consommée à la finalisation. En mode A, ``tranche`` est ``None`` — une
    tranche sera créée à la finalisation pour matérialiser l'engagement.
    """

    class Statut(models.TextChoices):
        PENDING = "pending", "En attente de réponse"
        ACCEPTED = "accepted", "Acceptée (réponse explicite)"
        AUTO_ACCEPTED = "auto_accepted", "Acceptée tacitement (24h écoulées)"
        REFUSED = "refused", "Refusée"
        OBSOLETE = "obsolete", "Obsolète (remplacée par une vague suivante)"

    funding_request = models.ForeignKey(
        LoanFundingRequest,
        on_delete=models.CASCADE,
        related_name="consent_requests",
    )
    lender = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="consent_requests_received",
    )
    tranche = models.ForeignKey(
        "savings.LenderTranche",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="consent_requests",
        help_text=(
            "Tranche cible (mode B). Null en mode A : une tranche sera créée "
            "à la finalisation pour matérialiser l'engagement."
        ),
    )
    montant_propose = money_field(
        help_text="Montant proposé à ce prêteur pour cette vague."
    )
    statut = models.CharField(
        max_length=16,
        choices=Statut.choices,
        default=Statut.PENDING,
        db_index=True,
    )
    deadline = models.DateTimeField(
        db_index=True,
        help_text=(
            "Date butoir individuelle (= created_at + funding.window_hours). "
            "Au-delà, le cron pose AUTO_ACCEPTED."
        ),
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date de la réponse explicite (None pour AUTO_ACCEPTED).",
    )
    refus_motif = models.TextField(
        blank=True, help_text="Motif facultatif fourni par le prêteur en cas de refus."
    )

    class Meta:
        ordering = ["funding_request", "-created_at"]
        verbose_name = "Demande de consentement prêteur"
        verbose_name_plural = "Demandes de consentement prêteur"
        indexes = [
            models.Index(fields=["lender", "statut"]),
            models.Index(fields=["statut", "deadline"]),
        ]
        # NB : pas de contrainte unique ``(funding_request, lender)`` — en mode B
        # un même prêteur peut couvrir plusieurs tranches sur le même crédit
        # (1 consent_request par tranche). La granularité tranche est nécessaire
        # pour le passage statut → ENGAGEE et la traçabilité du R1 (LOT 13).

    def __str__(self) -> str:
        return (
            f"Consent {self.lender.numero_membre} ← "
            f"{self.funding_request.loan.numero_dossier} · "
            f"{self.montant_propose} XAF · {self.statut}"
        )


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 9 : Partage 50/50 des intérêts crédit (§7.5)
# ---------------------------------------------------------------------------
#
# À chaque ``LoanRepayment`` posé par ``payments.services._hook_loan_repayment``,
# la portion intérêt de l'imputation est splittée :
#   • ``intérêt_coop = intérêt × (1 - lender.interest_share_rate)``  → revenu coop
#   • ``intérêt_pretteurs = intérêt × lender.interest_share_rate``   → réparti
#       entre les ``LenderAllocation`` au prorata de ``quote_part``.
#
# Une ``LenderInterestPayout`` est posée par allocation × imputation : c'est la
# brique d'historique pour le portail prêteur (§6 BUSINESS_RULES_2026).


class LenderInterestPayout(TimestampedModel):
    """Versement d'une part d'intérêts à un prêteur (refonte 2026 §7.5 / LOT 9).

    Une ligne par (allocation × imputation) : si un Payment touche 3 échéances
    et que le crédit a 2 prêteurs, on pose 3 × 2 = 6 ``LenderInterestPayout``.

    Le montant est immédiatement crédité au ``ClassicSavingsAccount`` du
    prêteur via une ``ClassicSavingsTransaction(TypeOp.INTERET_PRETEUR)`` —
    cette ligne sert d'historique métier (« quel prêteur a touché combien et
    sur quel crédit »), pas de ledger comptable.
    """

    allocation = models.ForeignKey(
        LenderAllocation,
        on_delete=models.PROTECT,
        related_name="interest_payouts",
    )
    installment = models.ForeignKey(
        LoanInstallment,
        on_delete=models.PROTECT,
        related_name="lender_interest_payouts",
        null=True,
        blank=True,
        help_text=(
            "Échéance dont la part intérêt a généré ce versement. NULL en "
            "mode CH-11 source — le versement a lieu à T0 (décaissement) et "
            "n'est rattaché à aucune échéance individuelle."
        ),
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="lender_interest_payouts",
        help_text=(
            "Paiement remboursement à l'origine de l'imputation qui a généré "
            "ce versement intérêt prêteur."
        ),
    )
    montant = money_field(
        help_text="Part d'intérêts versée au prêteur sur cette imputation (XAF)."
    )
    date = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Versement intérêt prêteur"
        verbose_name_plural = "Versements intérêt prêteur"
        indexes = [
            models.Index(fields=["allocation", "-date"]),
            models.Index(fields=["installment", "-date"]),
        ]

    def __str__(self) -> str:
        return (
            f"Payout {self.allocation.lender.numero_membre} · "
            f"{self.montant} XAF · {self.date:%Y-%m-%d}"
        )


# ---------------------------------------------------------------------------
# Refonte 2026 — LOT 10 : Voie d'éligibilité AVALISTE (§7.2)
# ---------------------------------------------------------------------------
#
# Un nouvel adhérent (non senior, donc inéligible Voie 1 SENIOR_BRC) peut
# soumettre une demande de crédit en désignant un avaliste — un membre
# ANCIEN qui se porte garant. La demande passe par :
#
#   EN_ATTENTE_AVALISTE → (avaliste accepte) → EN_INSTRUCTION
#                       → (avaliste refuse)  → REJETEE_AVALISTE (terminal)
#
# Identification double-clé : ``numero_membre`` + ``nom`` (case-insensitive).
# Vérifications avant création :
#   - le numéro existe
#   - le nom correspond
#   - le membre est ACTIF
#   - le membre est is_senior (ancienneté ≥ seniority.threshold_months)
#   - couverture épargne(borrower) + épargne(avaliste) ≥ montant × ratio
#     (``loans.avaliste.min_coverage_ratio``, défaut 1.00)
#
# Une fois ACCEPTED, l'avaliste **ne peut pas se rétracter** (Q13). En cas
# de défaut, R1 saisit borrower + avaliste (Q9.4, LOT 13).


class AvalisteConsent(TimestampedModel):
    """Consentement d'un avaliste sur une ``LoanRequest`` (refonte 2026 §7.2).

    1 ligne par LoanRequest engageant la voie AVALISTE. La saisie
    ``identification_*`` est conservée brute (telle que tapée par le
    demandeur) pour audit/anti-fraude — on n'y rejoue PAS la recherche.
    L'avaliste validé est tracé sur ``LoanRequest.avaliste`` (FK propre).
    """

    class Statut(models.TextChoices):
        PENDING = "pending", "En attente de réponse"
        ACCEPTED = "accepted", "Acceptée"
        REFUSED = "refused", "Refusée"

    loan_request = models.OneToOneField(
        LoanRequest,
        on_delete=models.CASCADE,
        related_name="avaliste_consent",
    )
    avaliste = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="avaliste_consents",
        help_text=(
            "Membre ancien désigné. Résolu via numero_membre + nom au moment "
            "de la création du consentement."
        ),
    )
    statut = models.CharField(
        max_length=12,
        choices=Statut.choices,
        default=Statut.PENDING,
        db_index=True,
    )

    # Snapshot des soldes utilisés pour le calcul de couverture (audit) :
    # gelés au moment de la demande pour qu'un dépôt/retrait ultérieur
    # n'invalide pas a posteriori la décision.
    epargne_borrower_at_request = money_field(
        default=ZERO,
        help_text="Cumul épargne (collecte + classique) du demandeur au moment de la demande.",
    )
    epargne_avaliste_at_request = money_field(
        default=ZERO,
        help_text="Cumul épargne (collecte + classique) de l'avaliste au moment de la demande.",
    )
    couverture_ratio = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        help_text=(
            "Ratio (épargne_borrower + épargne_avaliste) / montant_demande "
            "calculé au moment de la demande. Doit être ≥ "
            "``loans.avaliste.min_coverage_ratio`` (défaut 1.0000)."
        ),
    )

    # Trace brute des champs saisis (anti-fraude / litige).
    identification_numero_saisi = models.CharField(
        max_length=32,
        help_text="Numéro identification AVALISTE tapé par le demandeur (brut).",
    )
    identification_nom_saisi = models.CharField(
        max_length=200,
        help_text="Nom de famille AVALISTE tapé par le demandeur (brut, casse d'origine).",
    )

    responded_at = models.DateTimeField(
        null=True, blank=True, help_text="Date de réponse explicite (accept/refuse)."
    )
    refus_motif = models.TextField(
        blank=True, help_text="Motif facultatif si refus."
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Consentement avaliste"
        verbose_name_plural = "Consentements avaliste"
        indexes = [
            models.Index(fields=["avaliste", "statut"]),
            models.Index(fields=["statut", "-created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"Avaliste {self.avaliste.numero_membre} ← "
            f"LR#{self.loan_request_id} · {self.statut}"
        )


class JudicialEscalation(TimestampedModel):
    """Escalade judiciaire — phases D/E (refonte 2026 §9.3-9.4 / LOT 14).

    Posée quand la saisie épargne (R1, LOT 13) n'a pas suffi à solder un
    crédit en contentieux (``poursuite_judiciaire_at`` non NULL ET
    ``solde_restant > 0``). Représente l'engagement judiciaire (huissier
    d'abord, saisie de biens ensuite). 1 escalade par crédit (OneToOne).

    State machine :

      EN_INSTANCE                 ─── (admin saisit la décision) ────►  DECISION_RENDUE
        │                                                                  │
        │ (admin abandonne, irrécouvrable)                                 │ (exécution effective de la saisie biens)
        ▼                                                                  ▼
      CLASSEE_SANS_SUITE                                                EXECUTEE

    Modes de déclenchement (tunable ``loans.judicial_escalation.mode``) :
      - ``manual`` (défaut) : admin clique
      - ``auto`` : cron pose après ``delay_days`` jours de poursuite
      - ``hybrid`` : cron envoie un rappel à J-N, puis pose à J0

    Notes Q6 : pas de logique financière automatique en phase D — seulement
    la traçabilité humaine. La phase E (EXECUTEE) DOIT être saisie à la main
    par l'admin (décision validée + montant récupéré).
    """

    class Statut(models.TextChoices):
        EN_INSTANCE = "en_instance", "En instance (D — instruction huissier)"
        DECISION_RENDUE = (
            "decision_rendue",
            "Décision rendue (E — saisie biens autorisée)",
        )
        EXECUTEE = "executee", "Exécutée (E — biens saisis, recouvrement enregistré)"
        CLASSEE_SANS_SUITE = (
            "classee_sans_suite",
            "Classée sans suite (irrécouvrable)",
        )

    loan = models.OneToOneField(
        "loans.Loan",
        on_delete=models.PROTECT,
        related_name="judicial_escalation",
        help_text="Crédit objet de la procédure (1 escalade max par crédit).",
    )
    statut = models.CharField(
        max_length=24,
        choices=Statut.choices,
        default=Statut.EN_INSTANCE,
        db_index=True,
    )

    declenche_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="judicial_escalations_opened",
        help_text="Admin auteur (NULL si mode 'auto' déclenché par le cron).",
    )
    declenche_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    declenche_mode = models.CharField(
        max_length=16,
        default="manual",
        help_text='Mode de déclenchement: "manual", "auto", "hybrid".',
    )
    motif = models.TextField(
        help_text="Raison d'ouverture (rédaction admin / template auto).",
    )
    documents_attaches = models.JSONField(
        default=list,
        blank=True,
        help_text="Liste libre de références à des Documents (cf. members.Document).",
    )

    # Phase E — décision judiciaire saisie par admin.
    decision_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date de la décision judiciaire ; posée à DECISION_RENDUE.",
    )
    biens_saisissables = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Inventaire libre des biens autorisés à la saisie. Liste d'objets "
            "ex. [{'description': 'Mobylette', 'valeur_estimee': '120000'}]."
        ),
    )

    # Phase E — exécution effective + recouvrement.
    execution_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date d'exécution de la saisie (posée à EXECUTEE).",
    )
    montant_recouvre = money_field(
        default=ZERO,
        help_text=(
            "Montant effectivement recouvré après vente / cession des biens "
            "saisis. Décrémente ``Loan.solde_restant`` à l'exécution."
        ),
    )
    biens_saisis = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Inventaire effectif des biens saisis lors de l'exécution. "
            "Peut différer de ``biens_saisissables`` (subset, ou ajouts)."
        ),
    )

    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.CharField(
        max_length=64, blank=True, help_text='ex. "executee", "irrecouvrable".'
    )

    class Meta:
        ordering = ["-declenche_at"]
        verbose_name = "Escalade judiciaire"
        verbose_name_plural = "Escalades judiciaires"
        indexes = [
            models.Index(fields=["statut", "-declenche_at"]),
            models.Index(fields=["declenche_mode", "statut"]),
        ]

    def __str__(self) -> str:
        return f"Escalade {self.loan.numero_dossier} · {self.statut}"
