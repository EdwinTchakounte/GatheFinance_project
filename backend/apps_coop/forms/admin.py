from django.contrib import admin

from .models import FormSchema


@admin.register(FormSchema)
class FormSchemaAdmin(admin.ModelAdmin):
    list_display = ("kind", "version", "title", "is_active", "activated_at", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "description", "notes_admin")
    readonly_fields = ("created_at", "updated_at", "activated_at", "activated_by")
    ordering = ("kind", "-version")
