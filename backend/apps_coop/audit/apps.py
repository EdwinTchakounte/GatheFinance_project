from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.audit"
    label = "audit"
    verbose_name = "Audit & paramétrage système"
