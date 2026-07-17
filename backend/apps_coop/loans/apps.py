from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.loans"
    label = "loans"
    verbose_name = "Crédits"

    def ready(self):
        from . import signals  # noqa: F401 — enregistre les receivers
