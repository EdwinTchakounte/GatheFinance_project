from django.contrib import admin

from .models import AppSetting, AuditLog, BlockedIP


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "entite_type", "entite_id", "ip")
    list_filter = ("action", "entite_type", "created_at")
    search_fields = ("action", "entite_type", "user__email", "ip")
    date_hierarchy = "created_at"
    autocomplete_fields = ("user",)
    readonly_fields = tuple(f.name for f in AuditLog._meta.get_fields() if not f.many_to_many)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("cle", "valeur", "updated_at")
    search_fields = ("cle", "description")


@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    """Blacklist IP — l'admin peut bannir/débannir manuellement une IP.

    Bannir = ajouter une ligne (expires_at vide = permanent). Débannir =
    supprimer la ligne. Les bans auto (trafic anormal) apparaissent aussi ici.
    """

    list_display = ("ip", "auto", "reason", "expires_at", "created_at")
    list_filter = ("auto", "created_at")
    search_fields = ("ip", "reason")
    date_hierarchy = "created_at"
