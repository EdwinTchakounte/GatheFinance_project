from django.contrib import admin

from .models import EmailLog, EmailTemplate, Notification


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "objet", "actif", "updated_at")
    list_filter = ("actif",)
    search_fields = ("code", "objet")


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("template", "destinataire", "statut", "sent_at", "created_at")
    list_filter = ("statut", "created_at")
    search_fields = ("destinataire", "objet", "template__code")
    autocomplete_fields = ("template", "member")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "sent_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "lue", "created_at")
    list_filter = ("type", "lue", "created_at")
    search_fields = ("user__email", "message")
    autocomplete_fields = ("user",)
    date_hierarchy = "created_at"
