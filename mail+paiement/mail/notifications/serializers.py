"""Serializers for the notifications API."""
from rest_framework import serializers

from .models import Announcement, Notification


class NotificationReadSerializer(serializers.ModelSerializer):
    """Compact shape consumed by the portal / mobile notification list."""

    class Meta:
        model = Notification
        fields = ("id", "type", "message", "lien", "lue", "created_at")
        read_only_fields = fields


class AnnouncementReadSerializer(serializers.ModelSerializer):
    """Vue admin d'une annonce — listing + détail."""

    audience_display = serializers.CharField(
        source="get_audience_display", read_only=True
    )
    author_email = serializers.CharField(source="author.email", read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Announcement
        fields = (
            "id",
            "titre",
            "corps",
            "audience",
            "audience_display",
            "audience_member_ids",
            "lien",
            "image_url",
            "author",
            "author_email",
            "published_at",
            "expires_at",
            "recipients_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "audience_display",
            "author",
            "author_email",
            "published_at",
            "recipients_count",
            "created_at",
            "updated_at",
        )


class AnnouncementCreateSerializer(serializers.Serializer):
    """Body du POST admin — création d'une annonce (diffusion immédiate)."""

    titre = serializers.CharField(max_length=200)
    corps = serializers.CharField()
    audience = serializers.ChoiceField(
        choices=Announcement.Audience.choices,
        default=Announcement.Audience.ALL,
    )
    audience_member_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    lien = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    image = serializers.ImageField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        if (
            attrs.get("audience") == Announcement.Audience.SELECTION
            and not attrs.get("audience_member_ids")
        ):
            raise serializers.ValidationError(
                {
                    "audience_member_ids": (
                        "Au moins un identifiant membre est requis quand "
                        "l'audience est 'selection'."
                    )
                }
            )
        return attrs
