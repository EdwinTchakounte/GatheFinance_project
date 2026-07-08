"""Serializers — interactions sociales.

Deux niveaux de visibilite :
- Lecture publique (membres) : on masque le body des commentaires hidden
  par un placeholder ``[Commentaire masque]`` et on expose hidden=True
  pour que l'UI mobile le rende en italique grise.
- Lecture staff (admin) : on expose le vrai body + les metadonnees de
  masquage (`hidden_by`, `hidden_at`, `hidden_reason`).
"""
from __future__ import annotations

from rest_framework import serializers

from .models import ContentComment


HIDDEN_BODY_PLACEHOLDER = "[Commentaire masque]"


def _author_display(user) -> str:
    """Format human-readable du nom de l'auteur (priorise prenom + nom)."""
    if user is None:
        return "Anonyme"
    full = " ".join(filter(None, [user.first_name, user.last_name])).strip()
    return full or (user.email or user.username or "Membre")


class CommentSerializer(serializers.ModelSerializer):
    """Vue membre d'un commentaire — body masque si hidden=True.

    Pour un commentaire racine (``parent`` NULL), ``replies`` contient le fil
    de reponses (1 seul niveau, ordre chronologique). Pour une reponse,
    ``replies`` est toujours vide.
    """

    author_name = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = ContentComment
        fields = (
            "id",
            "parent_id",
            "body",
            "author_name",
            "created_at",
            "hidden",
            "is_mine",
            "replies",
            "reply_count",
        )
        read_only_fields = fields

    def get_author_name(self, obj) -> str:
        return _author_display(obj.user)

    def get_body(self, obj) -> str:
        if obj.hidden:
            return HIDDEN_BODY_PLACEHOLDER
        return obj.body

    def get_is_mine(self, obj) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.user_id == request.user.id

    def _visible_replies(self, obj) -> list:
        # ``obj.replies`` est prefetch cote vue (prefetch_related). On filtre
        # les reponses masquees pour les non-staff.
        request = self.context.get("request")
        is_staff = bool(request and request.user.is_authenticated and request.user.is_staff)
        replies = sorted(obj.replies.all(), key=lambda r: r.created_at)
        if not is_staff:
            replies = [r for r in replies if not r.hidden]
        return replies

    def get_replies(self, obj) -> list:
        if obj.parent_id is not None:
            return []  # 1 niveau : une reponse n'a pas de sous-reponses.
        return CommentSerializer(
            self._visible_replies(obj), many=True, context=self.context
        ).data

    def get_reply_count(self, obj) -> int:
        if obj.parent_id is not None:
            return 0
        return len(self._visible_replies(obj))


class AdminCommentSerializer(serializers.ModelSerializer):
    """Vue staff complete — expose le vrai body + meta masquage + contexte."""

    author_name = serializers.SerializerMethodField()
    author_email = serializers.CharField(source="user.email", read_only=True)
    hidden_by_email = serializers.SerializerMethodField()
    content_type_label = serializers.SerializerMethodField()

    class Meta:
        model = ContentComment
        fields = (
            "id",
            "parent_id",
            "body",
            "author_name",
            "author_email",
            "created_at",
            "updated_at",
            "hidden",
            "hidden_by_email",
            "hidden_at",
            "hidden_reason",
            "content_type_label",
            "object_id",
        )
        read_only_fields = fields

    def get_author_name(self, obj) -> str:
        return _author_display(obj.user)

    def get_hidden_by_email(self, obj) -> str | None:
        return obj.hidden_by.email if obj.hidden_by else None

    def get_content_type_label(self, obj) -> str:
        # On retourne `app_label.model` lisible (ex. `cms.blogpostpage`).
        ct = obj.content_type
        return f"{ct.app_label}.{ct.model}" if ct else ""


class CommentCreateSerializer(serializers.Serializer):
    """Validation du payload d'ecriture d'un commentaire (ou d'une reponse)."""

    body = serializers.CharField(
        min_length=1,
        max_length=ContentComment.MAX_BODY_LEN,
        trim_whitespace=True,
    )
    # Optionnel : id du commentaire racine auquel on repond (1 niveau).
    parent_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_body(self, value: str) -> str:
        v = value.strip()
        if not v:
            raise serializers.ValidationError("Le commentaire ne peut etre vide.")
        return v


class HideCommentSerializer(serializers.Serializer):
    """Payload admin pour masquer un commentaire (motif obligatoire)."""

    reason = serializers.CharField(
        min_length=1,
        max_length=500,
        trim_whitespace=True,
    )
