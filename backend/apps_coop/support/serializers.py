from __future__ import annotations

from rest_framework import serializers

from apps_coop.members.naming import full_name

from .models import SupportMessage, SupportThread


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ["id", "sender", "body", "read_by_recipient", "created_at"]
        read_only_fields = fields


class SupportThreadAdminSerializer(serializers.ModelSerializer):
    """Ligne de la boîte de réception admin (un fil par membre)."""

    member_id = serializers.IntegerField(source="member.id", read_only=True)
    member_numero = serializers.CharField(
        source="member.numero_membre", read_only=True
    )
    member_nom = serializers.SerializerMethodField()
    last_body = serializers.SerializerMethodField()
    staff_unread = serializers.SerializerMethodField()

    class Meta:
        model = SupportThread
        fields = [
            "id",
            "member_id",
            "member_numero",
            "member_nom",
            "last_message_at",
            "last_body",
            "staff_unread",
        ]

    def get_member_nom(self, obj) -> str:
        return full_name(obj.member.prenom, obj.member.nom)

    def get_last_body(self, obj) -> str:
        last = obj.messages.order_by("-created_at").first()
        return last.body[:120] if last else ""

    def get_staff_unread(self, obj) -> int:
        return obj.unread_for_staff()
