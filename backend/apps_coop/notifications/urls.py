"""Notifications API routes.

Mounted under ``/api/v1/notifications/`` by ``config/api_v1.py``.
"""
from django.urls import path

from . import admin_views, views


app_name = "coop_notifications"

urlpatterns = [
    path("", views.list_notifications, name="list"),
    path("announcements/", views.list_my_announcements, name="my-announcements"),
    path("read-all/", views.mark_all_read, name="read-all"),
    path("<int:pk>/read/", views.mark_read, name="read"),
    # Push — enregistrement du jeton d'appareil (bases FCM/APNs).
    path("devices/register/", views.register_device, name="device-register"),
    path("devices/unregister/", views.unregister_device, name="device-unregister"),
    # Préférences push par catégorie (opt-out).
    path("preferences/", views.notification_preferences, name="preferences"),
    # Admin — gestion des annonces broadcast.
    path(
        "admin/announcements/",
        admin_views.admin_announcements_list,
        name="admin-announcements-list",
    ),
    path(
        "admin/announcements/create/",
        admin_views.admin_announcements_create,
        name="admin-announcements-create",
    ),
    path(
        "admin/announcements/<int:pk>/",
        admin_views.admin_announcements_delete,
        name="admin-announcements-delete",
    ),
]
