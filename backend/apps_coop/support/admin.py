from django.contrib import admin

from .models import SupportMessage, SupportThread


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    fields = ("sender", "author", "body", "read_by_recipient", "created_at")
    readonly_fields = ("created_at",)


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = ("member", "last_message_at")
    search_fields = ("member__numero_membre", "member__nom", "member__prenom")
    inlines = [SupportMessageInline]
