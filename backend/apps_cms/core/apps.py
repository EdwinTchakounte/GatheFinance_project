from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_cms.core"
    label = "core"
    verbose_name = "Réglages du site"
