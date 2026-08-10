"""Serializers for the members domain.

`MembershipPublicSerializer` is what the public (anonymous) form on the website
POSTs into. The admin-side serializers are below.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import BRCDocument, Member, MembershipRequest

# Re-export the captcha verifier so we keep abuse protection equivalent to the
# legacy CMS form. The function is dependency-free and lives in apps_cms/forms
# for historical reasons; we can move it under `apps_coop.common.captcha`
# whenever we touch it again.
from apps_cms.forms.captcha import verify as verify_captcha


LANG_CHOICES = ("fr", "en")


STATUT_PRO_CHOICES = tuple(c[0] for c in MembershipRequest.StatutPro.choices)


_MAX_PIECE_SIZE = 5 * 1024 * 1024  # 5 MB par pièce — borne anti-abus.


def _validate_piece_size(value):
    """Raise ``ValidationError`` si la pièce dépasse ``_MAX_PIECE_SIZE``."""
    if value and value.size > _MAX_PIECE_SIZE:
        raise serializers.ValidationError(
            f"Le fichier est trop volumineux ({value.size // 1024} ko). "
            f"Taille maximum autorisée : {_MAX_PIECE_SIZE // 1024 // 1024} Mo."
        )
    return value


class MembershipPublicSerializer(serializers.Serializer):
    """Body of ``POST /api/forms/adhesion/`` — anonymous, captcha-protected.

    Champs alignés sur l'Article 2 du Règlement Intérieur :
      - identité (nom complet, email)
      - téléphone normal + WhatsApp
      - ville + lieu précis d'habitation
      - statut pro
      - contact d'urgence (nom, lien, téléphone)
      - motivation libre

    Pièces obligatoires uploadées par le demandeur (mobile + vitrine) :
    CNI recto, CNI verso, plan de localisation, photo d'identité.
    Le payload doit être encodé ``multipart/form-data``.
    """

    # Identity
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()

    # Coordonnées
    phone = serializers.CharField(max_length=40)
    whatsapp = serializers.CharField(max_length=40, required=False, allow_blank=True)

    # Localisation
    city = serializers.CharField(max_length=160)
    quartier_localite = serializers.CharField(max_length=200, required=False, allow_blank=True)

    # Statut social/pro
    statut_pro = serializers.ChoiceField(
        choices=STATUT_PRO_CHOICES,
        required=False,
        allow_blank=True,
    )

    # Contact d'urgence
    urgence_nom = serializers.CharField(max_length=200, required=False, allow_blank=True)
    urgence_lien = serializers.CharField(max_length=80, required=False, allow_blank=True)
    urgence_phone = serializers.CharField(max_length=40, required=False, allow_blank=True)

    message = serializers.CharField(required=False, allow_blank=True)
    language = serializers.ChoiceField(choices=LANG_CHOICES, default="fr")

    # Pièces — optionnelles à la candidature publique (vitrine peut
    # soumettre en JSON sans fichiers). La collecte finale des 4 pièces
    # (CNI recto/verso, plan localisation, photo identité) peut être
    # complétée par l'admin. Le mobile peut quand même envoyer les fichiers
    # en avance via multipart/form-data, ils seront acceptés et attachés.
    cni_recto = serializers.FileField(
        required=False, allow_null=True, validators=[_validate_piece_size],
    )
    cni_verso = serializers.FileField(
        required=False, allow_null=True, validators=[_validate_piece_size],
    )
    plan_localisation = serializers.FileField(
        required=False, allow_null=True, validators=[_validate_piece_size],
    )
    photo_identite = serializers.ImageField(
        required=False, allow_null=True, validators=[_validate_piece_size],
    )

    # Anti-spam — same scheme as ContactSerializer.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    captcha_token = serializers.CharField(write_only=True)
    captcha_answer = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs.get("website"):
            # Honeypot triggered — let the view return 201 silently.
            self.context["honeypot_tripped"] = True
        if not verify_captcha(attrs.get("captcha_token", ""), attrs.get("captcha_answer", "")):
            raise serializers.ValidationError(
                {"captcha_answer": "Réponse incorrecte. Merci de réessayer."}
            )
        return attrs

    def create(self, validated_data):
        meta = self.context.get("request_meta", {})

        # CH-4 — Le moteur FormSchema permet à l'admin d'ajouter des champs
        # supplémentaires au formulaire d'adhésion. On les capte depuis le
        # request.data brut (les fields du serializer ne couvrent que le
        # legacy), et on les répartit via ``apply_form_schema``.
        request = self.context.get("request")
        raw_payload = getattr(request, "data", {}) if request else {}
        # On passe le payload complet (avec les hardcoded) ET tous les
        # hardcoded keys au helper : il fait le split correctement et ignore
        # les required des hardcoded (déjà validés par DRF plus haut).
        _MEMBERSHIP_HARDCODED = {
            "name", "prenom", "email", "phone", "whatsapp", "city",
            "quartier_localite", "statut_pro", "urgence_nom",
            "urgence_lien", "urgence_phone", "message", "language",
            "cni_recto", "cni_verso", "plan_localisation", "photo_identite",
        }
        try:
            from apps_coop.forms.services import apply_form_schema

            _, extra_payload, schema_version = apply_form_schema(
                "adhesion",
                {k: v for k, v in raw_payload.items() if k not in {
                    # Anti-spam : jamais en extra_payload.
                    "website", "captcha_token", "captcha_answer",
                }},
                hardcoded_keys=_MEMBERSHIP_HARDCODED,
            )
        except Exception:  # noqa: BLE001 — toujours créer la requête (legacy)
            import logging
            logging.getLogger(__name__).exception(
                "apply_form_schema('adhesion') failed — falling back to legacy",
            )
            extra_payload, schema_version = {}, None

        # Le mobile envoie désormais `prenom` séparément ; la vitrine legacy ne
        # transmet qu'un `name` (nom complet) → prenom reste vide, l'admin le
        # renseigne à l'instruction. Quand prenom est fourni, on nettoie le nom
        # pour ne pas y ré-inclure le prénom en tête (dé-duplication à la source).
        _nom_in = validated_data["name"].strip()
        _prenom_in = ""
        if isinstance(raw_payload, dict) or hasattr(raw_payload, "get"):
            _prenom_in = (raw_payload.get("prenom") or "").strip()
        if _prenom_in and _nom_in.lower().startswith(_prenom_in.lower()):
            _stripped = _nom_in[len(_prenom_in):].strip()
            if _stripped:
                _nom_in = _stripped

        return MembershipRequest.objects.create(
            nom=_nom_in,
            prenom=_prenom_in,  # vide pour la vitrine legacy → admin complète
            email=validated_data["email"].strip().lower(),
            phone=validated_data.get("phone", "").strip(),
            whatsapp=validated_data.get("whatsapp", "").strip(),
            city=validated_data.get("city", "").strip(),
            quartier_localite=validated_data.get("quartier_localite", "").strip(),
            statut_pro=validated_data.get("statut_pro", "") or "",
            urgence_nom=validated_data.get("urgence_nom", "").strip(),
            urgence_lien=validated_data.get("urgence_lien", "").strip(),
            urgence_phone=validated_data.get("urgence_phone", "").strip(),
            motivation=validated_data.get("message", ""),
            language=validated_data.get("language", "fr"),
            cni_recto=validated_data.get("cni_recto"),
            cni_verso=validated_data.get("cni_verso"),
            plan_localisation=validated_data.get("plan_localisation"),
            photo_identite=validated_data.get("photo_identite"),
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent", "")[:400],
            extra_payload=extra_payload,
            form_schema_version=schema_version,
        )


# --- Admin-side serializers -------------------------------------------------


class MembershipRequestReadSerializer(serializers.ModelSerializer):
    """Compact admin view of a request — used by the admin dashboard listing."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    cni_recto_url = serializers.SerializerMethodField()
    cni_verso_url = serializers.SerializerMethodField()
    plan_localisation_url = serializers.SerializerMethodField()
    photo_identite_url = serializers.SerializerMethodField()

    class Meta:
        model = MembershipRequest
        fields = (
            "id", "nom", "prenom", "email",
            "phone", "whatsapp",
            "city", "quartier_localite", "statut_pro",
            "urgence_nom", "urgence_lien", "urgence_phone",
            "motivation",
            "cni_recto_url", "cni_verso_url",
            "plan_localisation_url", "photo_identite_url",
            "statut", "statut_display", "motif_rejet",
            "created_at", "date_decision",
        )
        read_only_fields = fields

    def _abs_url(self, fieldfile):
        if not fieldfile:
            return None
        request = self.context.get("request")
        try:
            url = fieldfile.url
        except (ValueError, AttributeError):
            return None
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_cni_recto_url(self, obj):
        return self._abs_url(obj.cni_recto)

    def get_cni_verso_url(self, obj):
        return self._abs_url(obj.cni_verso)

    def get_plan_localisation_url(self, obj):
        return self._abs_url(obj.plan_localisation)

    def get_photo_identite_url(self, obj):
        return self._abs_url(obj.photo_identite)


class MembershipApproveSerializer(serializers.Serializer):
    prenom = serializers.CharField(max_length=120, required=False, allow_blank=True)
    nom = serializers.CharField(max_length=200)


class MembershipRejectSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=2000)


class MemberCreateSerializer(serializers.Serializer):
    """M1 — Body du POST admin pour créer un membre depuis le dashboard."""

    nom = serializers.CharField(max_length=120)
    prenom = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)


class MemberReinscriptionConfirmSerializer(serializers.Serializer):
    """A2 — Body du POST admin pour acter la réinscription annuelle."""

    paid_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Montant encaissé (info — l'enregistrement du paiement passe par le flow Tara classique).",
    )
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class MemberReadSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)
    prochaine_reinscription_due = serializers.DateField(read_only=True)
    # LOT 1 (refonte 2026) — éligibilité crédit "Senior + BRC" (§7.1).
    seniority_months = serializers.IntegerField(read_only=True)
    is_senior = serializers.BooleanField(read_only=True)

    class Meta:
        model = Member
        fields = (
            "id", "numero_membre", "prenom", "nom", "email", "phone",
            "statut", "statut_display", "date_adhesion",
            "date_derniere_reinscription", "prochaine_reinscription_due",
            "seniority_months", "is_senior",
            "is_brc_member", "brc_validated_at",
        )
        read_only_fields = fields


# --- BRC (Broad Range Consulting) — refonte 2026 ----------------------------


class BRCDocumentReadSerializer(serializers.ModelSerializer):
    """Vue membre d'un justificatif BRC (sans expose les liens internes)."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = BRCDocument
        fields = (
            "id", "statut", "statut_display",
            "nom_original", "taille",
            "motif_rejet", "validated_at", "created_at",
        )
        read_only_fields = fields


class BRCDocumentAdminReadSerializer(serializers.ModelSerializer):
    """Vue admin (enrichie avec infos membre pour le listing back-office)."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    member_numero = serializers.CharField(source="member.numero_membre", read_only=True)
    member_nom = serializers.CharField(source="member.nom", read_only=True)
    member_prenom = serializers.CharField(source="member.prenom", read_only=True)
    fichier_url = serializers.SerializerMethodField()
    champ_source_display = serializers.SerializerMethodField()

    class Meta:
        model = BRCDocument
        fields = (
            "id", "member", "member_numero", "member_nom", "member_prenom",
            "fichier_url", "nom_original", "taille",
            "statut", "statut_display", "motif_rejet",
            "loan_request_id", "champ_source", "champ_source_display",
            "validated_by", "validated_at", "created_at",
        )
        read_only_fields = fields

    def get_champ_source_display(self, obj: BRCDocument) -> str:
        # Modularisation Lot 0.5 : le libellé vient du LABEL du champ dans le
        # FormSchema actif (générique, par coop), plus d'un dict de noms en dur.
        # Cache sur l'instance du serializer → 1 requête pour toute la liste.
        if not obj.champ_source:
            return "Dépôt direct par le membre"
        labels = getattr(self, "_field_labels_cache", None)
        if labels is None:
            from apps_coop.forms.field_flags import field_labels

            labels = field_labels("loan_request")
            self._field_labels_cache = labels
        return labels.get(obj.champ_source, obj.champ_source)

    def get_fichier_url(self, obj: BRCDocument) -> str:
        try:
            return obj.fichier.url
        except (ValueError, AttributeError):
            return ""
        # NB : on renvoie l'URL **relative** (`/media/...`). Le front l'utilise
        # comme src d'<img>/iframe ; next.js (admin :3202) proxifie /media/*
        # vers le backend interne. Renvoyer une absolute_uri ici embarquerait
        # l'host Docker interne (`backend:8000`) qui n'est pas résoluble par
        # le navigateur.


class BRCDocumentUploadSerializer(serializers.Serializer):
    """Body du POST membre — upload d'un justificatif BRC."""

    fichier = serializers.FileField()
    nom_original = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )


class BRCDocumentRejectSerializer(serializers.Serializer):
    """Body du POST admin — rejet d'un justificatif BRC."""

    motif = serializers.CharField(max_length=2000)


class BookletOrderReadSerializer(serializers.ModelSerializer):
    """Vue membre/portail d'une commande de carnet (lecture seule)."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        from .models import BookletOrder as _BookletOrder

        model = _BookletOrder
        fields = (
            "id", "statut", "statut_display",
            "date_impression", "date_delivrance",
            "annee",  # L7 — plusieurs carnets/an
            "created_at",
        )
        read_only_fields = fields


class BookletOrderAdminSerializer(serializers.ModelSerializer):
    """Vue admin d'une commande de carnet . inclut le membre + notes agence."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    member_id = serializers.IntegerField(source="member.id", read_only=True)
    member_nom = serializers.SerializerMethodField()
    member_prenom = serializers.CharField(source="member.prenom", read_only=True)
    member_numero = serializers.CharField(source="member.numero_membre", read_only=True)
    member_phone = serializers.CharField(source="member.phone", read_only=True)
    payment_id = serializers.IntegerField(source="payment.id", read_only=True)
    payment_montant = serializers.DecimalField(
        source="payment.montant", max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta:
        from .models import BookletOrder as _BookletOrder

        model = _BookletOrder
        fields = (
            "id", "statut", "statut_display",
            "date_impression", "date_delivrance",
            "notes_agence",
            "annee",  # L7 — plusieurs carnets/an
            "member_id", "member_nom", "member_prenom",
            "member_numero", "member_phone",
            "payment_id", "payment_montant",
            "created_at",
        )
        read_only_fields = tuple(f for f in fields if f != "notes_agence")

    def get_member_nom(self, obj) -> str:
        return obj.member.nom or ""
