"""Serializers for the loans domain — member-facing surface only for now.

Admin-side serializers (instruction, decision, payout) will land here when
the admin Next.js dashboard is wired.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Loan, LoanInstallment, LoanRequest


# Configurable later via AppSetting — kept tight for the MVP.
MIN_DUREE_MOIS = 3
MAX_DUREE_MOIS = 36
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
            "loan",
            "extra_payload",
            "attachments",
        )
        read_only_fields = fields

    def get_member(self, obj):
        m = getattr(obj, "member", None)
        if m is None:
            return None
        return {
            "id": m.id,
            "numero_membre": getattr(m, "numero_membre", "") or "",
            "nom": getattr(m, "nom", "") or "",
            "prenom": getattr(m, "prenom", "") or "",
            "telephone": getattr(m, "telephone", "") or "",
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
            "disbursed": already_disbursed,
            "disbursement_pending": disbursement_pending,
        }


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

    class Meta:
        model = Loan
        fields = (
            "id",
            "numero_dossier",
            "montant",
            "taux_interet",
            "duree_mois",
            "date_decaissement",
            "date_premiere_echeance",
            "montant_total_du",
            "solde_restant",
            "statut",
            "statut_display",
            "installments",
            "created_at",
        )
        read_only_fields = fields
