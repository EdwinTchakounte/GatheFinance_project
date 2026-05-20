"""Serializers for the notifications API."""
from rest_framework import serializers

from .models import Notification


class NotificationReadSerializer(serializers.ModelSerializer):
    """Compact shape consumed by the portal / mobile notification list."""

    class Meta:
        model = Notification
        fields = ("id", "type", "message", "lien", "lue", "created_at")
        read_only_fields = fields
