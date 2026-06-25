"""Enregistrement Django admin — utile pour debug recette."""
from django.contrib import admin

from .models import ContentComment, ContentReaction


@admin.register(ContentReaction)
class ContentReactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "content_type", "object_id", "created_at")
    list_filter = ("content_type",)
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user",)


@admin.register(ContentComment)
class ContentCommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "content_type",
        "object_id",
        "hidden",
        "created_at",
    )
    list_filter = ("hidden", "content_type")
    search_fields = ("user__email", "body")
    raw_id_fields = ("user", "hidden_by")
