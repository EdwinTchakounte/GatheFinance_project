"""Audit API.

Endpoints staff pour l'admin Next.js — édition du catalogue AppSettings
(refonte 2026 P2). Le AuditLog reste read-only via Django admin classique.
"""
from django.urls import path

from . import admin_views


app_name = "coop_audit"

urlpatterns = [
    path(
        "admin/settings/",
        admin_views.admin_settings_list,
        name="admin-settings-list",
    ),
    path(
        "admin/settings/<path:key>/",
        admin_views.admin_settings_update,
        name="admin-settings-update",
    ),
]
