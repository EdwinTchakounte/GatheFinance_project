from django.apps import AppConfig


class SavingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.savings"
    label = "savings"
    verbose_name = "Comptes d'épargne"
