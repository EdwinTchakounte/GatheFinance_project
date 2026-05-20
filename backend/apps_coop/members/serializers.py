"""Serializers for the members domain.

`MembershipPublicSerializer` is what the public (anonymous) form on the website
POSTs into. The admin-side serializers are below.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Member, MembershipRequest

# Re-export the captcha verifier so we keep abuse protection equivalent to the
# legacy CMS form. The function is dependency-free and lives in apps_cms/forms
# for historical reasons; we can move it under `apps_coop.common.captcha`
# whenever we touch it again.
from apps_cms.forms.captcha import verify as verify_captcha


LANG_CHOICES = ("fr", "en")


STATUT_PRO_CHOICES = tuple(c[0] for c in MembershipRequest.StatutPro.choices)


class MembershipPublicSerializer(serializers.Serializer):
    """Body of ``POST /api/forms/adhesion/`` — anonymous, captcha-protected.

    Champs alignés sur l'Article 2 du Règlement Intérieur :
      - identité (nom complet, email)
      - téléphone normal + WhatsApp
      - ville + lieu précis d'habitation
      - statut pro
      - contact d'urgence (nom, lien, téléphone)
      - motivation libre

    Les pièces justificatives (CNI, plan de localisation) sont remises à
    l'entretien physique (Article 3) et uploadées par l'admin.
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
        return MembershipRequest.objects.create(
            nom=validated_data["name"].strip(),
            prenom="",  # admin will fill during instruction
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
            ip_address=meta.get("ip_address"),
            user_agent=meta.get("user_agent", "")[:400],
        )


# --- Admin-side serializers -------------------------------------------------


class MembershipRequestReadSerializer(serializers.ModelSerializer):
    """Compact admin view of a request — used by the admin dashboard listing."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = MembershipRequest
        fields = (
            "id", "nom", "prenom", "email",
            "phone", "whatsapp",
            "city", "quartier_localite", "statut_pro",
            "urgence_nom", "urgence_lien", "urgence_phone",
            "motivation",
            "date_entretien", "entretien_avis", "entretien_favorable",
            "statut", "statut_display", "motif_rejet",
            "created_at", "date_decision",
        )
        read_only_fields = fields


class MembershipApproveSerializer(serializers.Serializer):
    prenom = serializers.CharField(max_length=120, required=False, allow_blank=True)
    nom = serializers.CharField(max_length=200)


class MembershipRejectSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=2000)


class MemberReadSerializer(serializers.ModelSerializer):
    statut_display = serializers.CharField(source="get_statut_display", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Member
        fields = (
            "id", "numero_membre", "prenom", "nom", "email", "phone",
            "statut", "statut_display", "date_adhesion",
        )
        read_only_fields = fields


class BookletOrderReadSerializer(serializers.ModelSerializer):
    """Vue membre/portail d'une commande de carnet (lecture seule)."""

    statut_display = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        from .models import BookletOrder as _BookletOrder

        model = _BookletOrder
        fields = (
            "id", "statut", "statut_display",
            "date_impression", "date_delivrance",
            "created_at",
        )
        read_only_fields = fields
