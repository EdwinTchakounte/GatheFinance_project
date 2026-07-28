"""Serializers for the loans domain — member-facing surface only for now.

Admin-side serializers (instruction, decision, payout) will land here when
the admin Next.js dashboard is wired.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Loan, LoanInstallment, LoanRequest


# Aucun plancher réglementaire sur la durée : un crédit remboursé plus vite est
# autorisé. La SEULE contrainte « max selon le montant » (paliers Art. 7) est
# appliquée à l'APPROBATION — ``services.approuver_demande`` recalcule la durée
# via ``duration_months_for(montant)`` et l'écrase sur le Loan. Au submit on
# borne la durée à l'intervalle réglementaire [2, 9] mois (paliers Art. 7 : de
# 2 mois pour le 1er palier à 9 mois pour le dernier). Le client envoie de toute
# façon une durée dérivée du montant (donc dans cet intervalle) ; ce garde-fou
# rejette une valeur hors-bornes forgée à la main.
MIN_DUREE_MOIS = 2
MAX_DUREE_MOIS = 9
MIN_MONTANT_XAF = 5000


class LoanRequestSubmitSerializer(serializers.Serializer):
    """Body of ``POST /api/v1/loans/requests/``.

    Refonte 2026 (LOT 15) : champs optionnels pour les voies AVALISTE et
    CAMPAIGN. Si le demandeur est senior+BRC, ces champs sont ignorés (voie
    1 directe). Sinon, le routeur ``evaluate_routes`` cherche la voie qui
    matche les champs fournis.
    """

    montant_demande = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=MIN_MONTANT_XAF,
    )
    duree_mois = serializers.IntegerField(
        min_value=MIN_DUREE_MOIS,
        max_value=MAX_DUREE_MOIS,
    )
    motif = serializers.CharField(max_length=2000, allow_blank=False)

    # L5 — N° CNI du demandeur (Règlement condition 1). Optionnel au niveau API
    # pour ne pas casser les intégrations ; le front le présente comme attendu.
    cni_demandeur = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    # Voie AVALISTE — optionnel (§7.2 BUSINESS_RULES_2026).
    avaliste_numero = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )
    avaliste_nom = serializers.CharField(
        max_length=200, required=False, allow_blank=True
    )

    # Voie CAMPAIGN — optionnel (§8 BUSINESS_RULES_2026).
    campaign_id = serializers.IntegerField(required=False, allow_null=True)
    profil_cible = serializers.CharField(
        max_length=64, required=False, allow_blank=True
    )

    # Voie GARANTIE MATÉRIELLE (L4) — fallback sans avaliste. Le titre de
    # propriété est uploadé séparément (attachment Document schema_field_id
    # 'titre_propriete') ; la valeur est évaluée par l'admin.
    garantie_materielle = serializers.BooleanField(required=False, default=False)
    garantie_description = serializers.CharField(
        max_length=2000, required=False, allow_blank=True
    )

    # CH-9 — Moyen de réception choisi à la soumission.
    moyen_reception = serializers.ChoiceField(
        choices=[("tara_om", "Tara OM"), ("tara_momo", "Tara MoMo"), ("agence_especes", "Agence espèces")],
        required=False,
        allow_blank=True,
    )
    recipient_phone = serializers.CharField(
        max_length=32, required=False, allow_blank=True
    )

    def validate(self, attrs):
        moyen = attrs.get("moyen_reception") or ""
        phone = (attrs.get("recipient_phone") or "").strip()
        if moyen in ("tara_om", "tara_momo") and not phone:
            raise serializers.ValidationError(
                {"recipient_phone": "Requis pour un décaissement Tara Mobile Money."}
            )
        if moyen == "agence_especes" and phone:
            # Coherence : on n'attend pas de numéro pour un retrait espèces.
            attrs["recipient_phone"] = ""
        return attrs


class LoanRequestReadSerializer(serializers.ModelSerializer):
    """Portal + admin display — `loan` exposé pour l'admin (décaissement)."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    loan = serializers.SerializerMethodField()
    # Sociétaire qui a soumis la demande : indispensable pour l'admin
    # (savoir qui encaisser, qui contacter, vérifier l'identité).
    member = serializers.SerializerMethodField()
    # Réponses CFP Broad Range + CGA + autres champs FormSchema → l'admin
    # voit ces données dans la carte "Profil emprunteur" pour valider.
    extra_payload = serializers.JSONField(read_only=True)
    # Pièces justificatives uploadées (attestation CFP, carte CGA, etc.) —
    # indexées par schema_field_id pour relier au champ source.
    attachments = serializers.SerializerMethodField()
    # Frais d'étude applicables (pilotés admin via FeeType.DEMANDE_CREDIT) —
    # exposés pour que les clients (ex. mobile « payer plus tard ») affichent et
    # règlent le bon montant. Le backend reste autoritaire à l'`init` du paiement.
    frais_etude_montant = serializers.SerializerMethodField()
    # Porte des frais 2026 — de quoi que le client choisisse son canal SANS un
    # second aller-retour : la déduction épargne est le canal par défaut, mais
    # elle n'est proposable que si le retirable couvre les frais (ni le
    # placement ni l'épargne gelée en garantie ne sont ponctionnables).
    epargne_disponible_frais = serializers.SerializerMethodField()
    # Frais de carnet encore dus pour cette demande (bénéficiaire campagne sans
    # carnet). "0" sinon. Permet à l'admin d'encaisser étude + carnet à la
    # demande de crédit (2 paiements distincts, même étape).
    carnet_fee_due = serializers.SerializerMethodField()
    # Voie d'éligibilité empruntée (senior_brc / avaliste / campagne /
    # garantie_materielle), dérivée de l'état de la demande — pour prévisualiser
    # « le mode employé » sur chaque crédit (liste + détail admin, mobile).
    voie = serializers.SerializerMethodField()
    voie_display = serializers.SerializerMethodField()
    # Montant que l'AVALISTE doit couvrir sur ce crédit (= le manque : montant −
    # épargne dispo du demandeur). Exposé au demandeur ET repris côté avaliste
    # (montant_gele du mandat) pour que les deux connaissent l'engagement.
    avaliste_montant_a_couvrir = serializers.SerializerMethodField()

    class Meta:
        model = LoanRequest
        fields = (
            "id",
            "member",
            "montant_demande",
            "duree_mois",
            "motif",
            "statut",
            "statut_display",
            "motif_rejet",
            "montant_revise",
            "duree_revisee",
            "date_soumission",
            "date_decision",
            # L6 — échéance indicative d'étude commission
            "date_limite_etude",
            "frais_etude_montant",
            "frais_demande_credit_paye",
            "epargne_disponible_frais",
            "carnet_fee_due",
            # Voie + montant avaliste à couvrir (prévisualisation du mode).
            "voie",
            "voie_display",
            "avaliste_montant_a_couvrir",
            "loan",
            "extra_payload",
            "attachments",
            # L4 — garantie matérielle
            "garantie_materielle",
            "garantie_description",
            "garantie_valeur_estimee",
            # Réforme garantie — gel demandeur (+ motif lisible, 2026-07)
            "montant_gele_demandeur",
            "motif_gel_demandeur",
            # L5 — n° CNI demandeur
            "cni_demandeur",
        )
        read_only_fields = fields

    # Libellés lisibles des voies (aligné sur EligibilityRoute).
    _VOIE_LABELS = {
        "campagne": "Campagne",
        "avaliste": "Avaliste",
        "garantie_materielle": "Garantie matérielle",
        "senior_brc": "BRC / ancienneté",
    }

    def _derive_voie(self, obj) -> str:
        """Voie empruntée, dérivée de l'état de la demande (fiable sans stockage).

        Ordre = signaux les plus spécifiques d'abord : campagne (FK), avaliste
        (consentement OU désignation OU statut avaliste), garantie matérielle,
        sinon BRC/ancienneté (voie SENIOR_BRC, incl. auto-couverture épargne).
        """
        if getattr(obj, "microcampaign_id", None):
            return "campagne"
        statut = getattr(obj, "statut", "")
        has_consent = hasattr(obj, "avaliste_consent")
        designe = bool((getattr(obj, "avaliste_numero_saisi", "") or "").strip())
        if has_consent or designe or statut in (
            LoanRequest.Statut.EN_ATTENTE_AVALISTE,
            LoanRequest.Statut.REJETEE_AVALISTE,
        ):
            return "avaliste"
        if getattr(obj, "garantie_materielle", False):
            return "garantie_materielle"
        return "senior_brc"

    def get_voie(self, obj):
        return self._derive_voie(obj)

    def get_voie_display(self, obj):
        return self._VOIE_LABELS.get(self._derive_voie(obj), "—")

    def get_avaliste_montant_a_couvrir(self, obj):
        """Montant à couvrir par l'avaliste. Autoritaire depuis le consentement
        s'il existe (``montant_caution``), sinon projeté = manque = montant −
        épargne classique dispo du demandeur. "0" si la voie n'est pas avaliste."""
        from decimal import Decimal

        if self._derive_voie(obj) != "avaliste":
            return "0"
        consent = getattr(obj, "avaliste_consent", None)
        if consent is not None:
            return str(consent.montant_caution)
        try:
            from .avaliste_services import _member_available_savings

            dispo = _member_available_savings(obj.member)
        except Exception:  # noqa: BLE001
            dispo = Decimal("0")
        manque = Decimal(obj.montant_demande) - Decimal(dispo)
        return str(manque if manque > 0 else Decimal("0"))

    def get_frais_etude_montant(self, obj):
        # Frais RÉELLEMENT applicables à CETTE demande : override campagne si
        # la LR est rattachée à une micro-campagne (montant dynamique fixé à la
        # création — 0 = gratuit), sinon le tarif standard DEMANDE_CREDIT. Le
        # dashboard (paiement manuel) et les clients lisent ce montant : sans ce
        # rattachement, une demande de campagne affichait toujours le 5000
        # générique au lieu du tarif de sa campagne.
        from .services import study_fee_for

        montant = study_fee_for(getattr(obj, "microcampaign", None))
        return str(montant)

    def get_carnet_fee_due(self, obj):
        """Frais de carnet dus (bénéficiaire campagne sans carnet), sinon "0"."""
        from .services import campaign_member_needs_carnet, carnet_fee_amount

        member = getattr(obj, "member", None)
        if member is not None and campaign_member_needs_carnet(member):
            return str(carnet_fee_amount())
        return "0"

    def get_epargne_disponible_frais(self, obj):
        """Part de l'épargne classique réellement ponctionnable pour les frais.

        Le client compare ce montant à ``frais_etude_montant`` pour savoir s'il
        peut pré-sélectionner la déduction ou s'il doit basculer sur agence /
        mobile money. "0" = pas de compte classique, ou tout est placé/gelé.
        """
        from apps_coop.savings.models import ClassicSavingsAccount
        from apps_coop.savings.services import classic_withdrawable

        account = ClassicSavingsAccount.objects.filter(member=obj.member).first()
        if account is None:
            return "0"
        return str(classic_withdrawable(account))

    def get_member(self, obj):
        m = getattr(obj, "member", None)
        if m is None:
            return None
        # Le model Django utilise `phone` ; on expose `telephone` cote API
        # pour rester aligne sur la nomenclature des autres endpoints.
        return {
            "id": m.id,
            "numero_membre": getattr(m, "numero_membre", "") or "",
            "nom": getattr(m, "nom", "") or "",
            "prenom": getattr(m, "prenom", "") or "",
            "telephone": getattr(m, "phone", "") or "",
            # Email de l'adhérent (via le User lié) — sert la colonne « E-mail »
            # de la liste admin (masquée par défaut, activable au besoin) et le
            # contact direct depuis le cash-in.
            "email": getattr(getattr(m, "user", None), "email", "") or "",
        }

    def get_attachments(self, obj):
        """Liste les Documents indexés (schema_field_id, file URL, taille).
        L'admin peut cliquer pour prévisualiser/télécharger chaque pièce.
        """
        try:
            from apps_coop.members.models import Document
        except Exception:  # noqa: BLE001
            return []
        request = self.context.get("request")
        out = []
        qs = Document.objects.filter(
            entite_liee_type="LoanRequest",
            entite_liee_id=obj.id,
        ).order_by("schema_field_id", "-id")
        for d in qs:
            url = d.fichier.url if d.fichier else None
            if url and request is not None and not url.startswith("http"):
                url = request.build_absolute_uri(url)
            out.append({
                "id": d.id,
                "schema_field_id": d.schema_field_id,
                "nom_original": d.nom_original,
                "taille": d.taille,
                "url": url,
            })
        return out

    def get_loan(self, obj):
        """Renvoie un mini-objet du Loan associé (si créé). `decaissement` indique
        si un Payment(type=decaissement, statut=valide) existe déjà.
        """
        loan = getattr(obj, "loan", None)
        if loan is None:
            return None
        # Lazy import to avoid cycle
        from apps_coop.payments.models import Payment

        already_disbursed = Payment.objects.filter(
            loan=loan,
            type=Payment.Type.DECAISSEMENT,
            statut=Payment.Statut.VALIDE,
        ).exists()
        disbursement_pending = Payment.objects.filter(
            loan=loan,
            type=Payment.Type.DECAISSEMENT,
            statut=Payment.Statut.EN_ATTENTE,
        ).exists()
        return {
            "id": loan.id,
            "numero_dossier": loan.numero_dossier,
            "statut": loan.statut,
            "date_decaissement": loan.date_decaissement.isoformat(),
            "date_butoire": (
                loan.date_butoire.isoformat() if loan.date_butoire else None
            ),
            "disbursed": already_disbursed,
            "disbursement_pending": disbursement_pending,
        }


class AdminLoanRequestReadSerializer(LoanRequestReadSerializer):
    """Variante ADMIN — expose en plus les champs de la visite terrain.

    ``field_visit_note`` est le compte-rendu INTERNE de l'agent (observations
    candides sur le demandeur / son activité). Il ne doit JAMAIS transiter par
    un endpoint membre : on le réserve à cette sous-classe, utilisée uniquement
    par les vues staff/comité. ``field_visit_outcome`` débloque le bouton
    « Décision définitive » côté dashboard.
    """

    class Meta(LoanRequestReadSerializer.Meta):
        fields = LoanRequestReadSerializer.Meta.fields + (
            "field_visit_done_at",
            "field_visit_outcome",
            "field_visit_note",
        )
        read_only_fields = fields


class LoanInstallmentReadSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = LoanInstallment
        fields = (
            "id",
            "numero_echeance",
            "date_echeance",
            "montant_capital",
            "montant_interets",
            "montant_total",
            "montant_paye",
            "statut",
            "statut_display",
        )
        read_only_fields = fields


class LoanRequestDecideSerializer(serializers.Serializer):
    """Body of ``POST /api/v1/loans/requests/{id}/decide/`` — comité chair only."""

    decision = serializers.ChoiceField(choices=["approuvee", "rejetee"])
    # Required for approval, ignored otherwise.
    taux_annuel = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        required=False,
        min_value=0,
        max_value=1,
        help_text="Ex. 0.12 pour 12 %/an. Requis pour approbation.",
    )
    date_premiere_echeance = serializers.DateField(
        required=False,
        help_text="Date de l'échéance #1. Requis pour approbation.",
    )
    # Required for rejection.
    motif_rejet = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )
    # G4 — privilège accordé par le comité pour un crédit à découvert (facultatif).
    privilege_accorde = serializers.BooleanField(required=False, default=False)
    privilege_motif = serializers.CharField(
        required=False, allow_blank=True, max_length=2000, default=""
    )

    def validate(self, attrs):
        if attrs["decision"] == "approuvee":
            if not attrs.get("taux_annuel"):
                raise serializers.ValidationError({"taux_annuel": "Requis pour approuver."})
            if not attrs.get("date_premiere_echeance"):
                raise serializers.ValidationError(
                    {"date_premiere_echeance": "Requis pour approuver."}
                )
        elif attrs["decision"] == "rejetee":
            if not attrs.get("motif_rejet", "").strip():
                raise serializers.ValidationError({"motif_rejet": "Requis pour rejeter."})
        return attrs


class LoanRenewalRequestSerializer(serializers.Serializer):
    """Body of ``POST /api/v1/loans/{id}/renewal/`` — membre actif.

    Règlement, Article 10 : la reconduction accorde un mois supplémentaire fixe.
    ``nouvelle_duree_mois`` reste accepté en option pour rétro-compat (admin
    Django pourrait demander +2 mois exceptionnellement) ; absent = 1 mois.
    """

    interets_au_comptant = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Si True, le membre verse les intérêts cash à la reconduction → taux 10 %. "
            "Sinon les intérêts sont reportés avec le capital → taux 15 % (Article 11)."
        ),
    )
    nouvelle_duree_mois = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=12,
        help_text="Optionnel — par défaut 1 mois conformément à l'Article 10.",
    )


class LoanRenewalReadSerializer(serializers.Serializer):
    """Compact view returned to the portal after creation."""

    id = serializers.IntegerField(read_only=True)
    loan_id = serializers.IntegerField(read_only=True)
    nouvelle_duree_mois = serializers.IntegerField(read_only=True)
    statut = serializers.CharField(read_only=True)
    date_demande = serializers.DateTimeField(read_only=True)
    frais_reconduction_payment_id = serializers.IntegerField(read_only=True, allow_null=True)

    # Volet « intérêts au comptant » : ce que le membre doit verser, et si
    # c'est fait. Sans ces champs, les clients affichaient « tu verses les
    # intérêts maintenant » sans jamais pouvoir proposer de payer.
    interets_au_comptant = serializers.BooleanField(read_only=True)
    interets_dus = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    montant_a_reconduire_snapshot = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    interets_payes = serializers.BooleanField(read_only=True)
    interets_payes_at = serializers.DateTimeField(read_only=True, allow_null=True)
    reste_a_payer = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    numero_dossier = serializers.CharField(read_only=True, required=False)


class LoanRenewalDecideSerializer(serializers.Serializer):
    """Body of ``POST /api/v1/loans/renewals/{id}/decide/`` — comité."""

    decision = serializers.ChoiceField(choices=["approuvee", "rejetee"])
    taux_annuel = serializers.DecimalField(
        max_digits=5,
        decimal_places=4,
        required=False,
        min_value=0,
        max_value=1,
        help_text="Requis pour `decision=approuvee`. Ex. 0.12 pour 12 %/an.",
    )
    date_premiere_echeance = serializers.DateField(
        required=False,
        help_text="Requis pour `decision=approuvee`.",
    )
    motif_rejet = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Requis pour `decision=rejetee`.",
    )

    def validate(self, attrs):
        if attrs["decision"] == "approuvee":
            if attrs.get("taux_annuel") is None:
                raise serializers.ValidationError({"taux_annuel": "Requis pour approuver."})
            if not attrs.get("date_premiere_echeance"):
                raise serializers.ValidationError(
                    {"date_premiere_echeance": "Requis pour approuver."}
                )
        elif attrs["decision"] == "rejetee":
            if not (attrs.get("motif_rejet") or "").strip():
                raise serializers.ValidationError({"motif_rejet": "Requis pour rejeter."})
        return attrs


_PAYOUT_NETWORKS = {"MTN", "ORANGE", "WAVE", "AIRTEL"}


class LoanDisburseSerializer(serializers.Serializer):
    """Body of ``POST /api/v1/loans/{id}/disburse/`` — staff/admin only.

    Deux modes :

      - ``manuel`` (par défaut) — virement bancaire ou espèces. Requis :
        ``reference_externe`` (le numéro du virement / reçu).
      - ``tara`` — payout Mobile Money via Tara. Requis : ``recipient_phone``
        et ``network``. Crée un Payment ``en_attente`` ; le webhook Tara le
        passera à ``valide`` et déclenchera ``_hook_decaissement``.
    """

    mode = serializers.ChoiceField(choices=["manuel", "tara"], default="manuel")
    # Manuel
    reference_externe = serializers.CharField(max_length=64, required=False, allow_blank=True)
    note = serializers.CharField(allow_blank=True, max_length=500, required=False)
    # Tara
    recipient_phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    network = serializers.CharField(max_length=16, required=False, allow_blank=True)

    def validate_network(self, value: str) -> str:
        if not value:
            return value
        upper = value.upper()
        if upper not in _PAYOUT_NETWORKS:
            raise serializers.ValidationError(
                f"Network {value!r} non supporté. Attendu : {sorted(_PAYOUT_NETWORKS)}."
            )
        return upper

    def validate(self, attrs):
        mode = attrs.get("mode", "manuel")
        if mode == "manuel":
            if not (attrs.get("reference_externe") or "").strip():
                raise serializers.ValidationError(
                    {"reference_externe": "Requis pour un décaissement manuel."}
                )
        elif mode == "tara":
            phone = (attrs.get("recipient_phone") or "").strip()
            if not phone:
                raise serializers.ValidationError(
                    {"recipient_phone": "Requis pour un payout Tara."}
                )
            if not (attrs.get("network") or "").strip():
                raise serializers.ValidationError(
                    {"network": "Requis pour un payout Tara."}
                )
        return attrs


class LoanReadSerializer(serializers.ModelSerializer):
    """Portal display of an active credit, with its installment schedule."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    installments = LoanInstallmentReadSerializer(many=True, read_only=True)
    # Apport personnel gelé transférable pour solder ce crédit (2026-07).
    apport_gele = serializers.DecimalField(
        source="loan_request.montant_gele_demandeur",
        max_digits=14,
        decimal_places=0,
        read_only=True,
        default=0,
    )
    apport_gele_motif = serializers.CharField(
        source="loan_request.motif_gel_demandeur",
        read_only=True,
        default="",
    )
    # Rang du crédit dans l'historique DU MEMBRE (1 = premier crédit ouvert…).
    # Sert à un libellé parlant côté client (« Crédit n°1 · #GF-… ») en plus du
    # numéro de dossier technique, notamment sur la card de clôture.
    numero_ordre = serializers.SerializerMethodField()

    def get_numero_ordre(self, obj) -> int:
        # 1-based, par ordre de création chez ce membre. Petit volume par membre
        # → le count par crédit reste négligeable.
        return (
            Loan.objects.filter(member_id=obj.member_id, id__lte=obj.id).count()
        )

    # Gouvernance G3 — criticité (avis souple, dérivée du découvert tracé).
    criticite = serializers.SerializerMethodField()
    criticite_display = serializers.SerializerMethodField()

    def get_criticite(self, obj) -> str:
        from .criticality_services import credit_criticality

        return credit_criticality(obj)

    def get_criticite_display(self, obj) -> str:
        from .criticality_services import credit_criticality_label

        return credit_criticality_label(obj)

    # Date de soumission de la demande d'origine (affichée sur la card crédit).
    date_soumission = serializers.SerializerMethodField()

    def get_date_soumission(self, obj) -> str | None:
        lr = getattr(obj, "loan_request", None)
        d = getattr(lr, "date_soumission", None) if lr else None
        return d.isoformat() if d else None

    class Meta:
        model = Loan
        fields = (
            "id",
            "numero_dossier",
            "numero_ordre",
            "montant",
            "taux_interet",
            "duree_mois",
            "date_soumission",
            "date_decaissement",
            "date_premiere_echeance",
            "date_butoire",
            "montant_total_du",
            "solde_restant",
            "statut",
            "statut_display",
            "installments",
            "apport_gele",
            "apport_gele_motif",
            # Gouvernance G2 — décomposition couverture / découvert.
            "montant_gage",
            "montant_decouvert",
            # Gouvernance G3 — criticité (avis souple).
            "criticite",
            "criticite_display",
            # Gouvernance G4 — privilège accordé par le comité (tracé).
            "privilege_accorde",
            "privilege_motif",
            "created_at",
        )
        read_only_fields = fields
