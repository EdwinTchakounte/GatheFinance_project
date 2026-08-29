from django.apps import AppConfig


class SpecialCollectionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.special_collections"
    label = "special_collections"
    verbose_name = "Collectes particulières (caisse scolaire, tontine)"
