"""Notifications API routes.

Mounted under ``/api/v1/notifications/`` by ``config/api_v1.py``.
"""
from django.urls import path

from . import admin_views, views


app_name = "coop_notifications"

urlpatterns = [
    path("", views.list_notifications, name="list"),
    path("read-all/", views.mark_all_read, name="read-all"),
    path("<int:pk>/read/", views.mark_read, name="read"),
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
