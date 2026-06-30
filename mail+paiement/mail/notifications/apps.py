from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps_coop.notifications"
    label = "coop_notifications"
    verbose_name = "Notifications & emails"
