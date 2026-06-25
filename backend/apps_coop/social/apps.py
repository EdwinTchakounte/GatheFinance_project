from django.apps import AppConfig


class SocialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.social"
    label = "social"
    verbose_name = "Interactions sociales (likes & commentaires)"
