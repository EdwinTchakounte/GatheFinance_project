"""Audit API.

Endpoints staff pour l'admin Next.js — édition du catalogue AppSettings
(refonte 2026 P2). Le AuditLog reste read-only via Django admin classique.
"""
from django.urls import path

from . import admin_views, cron_admin_views, log_admin_views


app_name = "coop_audit"

urlpatterns = [
    # Journal d'audit (consultation centralisee de toutes les actions tracees).
    path(
        "admin/logs/",
        log_admin_views.admin_audit_logs_list,
        name="admin-audit-logs-list",
    ),
    path(
        "admin/logs/facets/",
        log_admin_views.admin_audit_logs_facets,
        name="admin-audit-logs-facets",
    ),
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
    # CooperativeAsset (règlement intérieur PDF — singleton)
    path(
        "admin/cooperative-asset/",
        admin_views.admin_cooperative_asset_get,
        name="admin-cooperative-asset",
    ),
    path(
        "admin/cooperative-asset/reglement/",
        admin_views.admin_cooperative_asset_upload_reglement,
        name="admin-cooperative-asset-reglement",
    ),
    # Cron schedules — édition cadence + run-now + reset (recette)
    path(
        "admin/cron-schedules/",
        cron_admin_views.admin_cron_schedules_list,
        name="admin-cron-list",
    ),
    path(
        "admin/cron-schedules/reset-defaults/",
        cron_admin_views.admin_cron_schedules_reset_defaults,
        name="admin-cron-reset",
    ),
    path(
        "admin/cron-schedules/<str:name>/",
        cron_admin_views.admin_cron_schedules_update,
        name="admin-cron-update",
    ),
    path(
        "admin/cron-schedules/<str:name>/run-now/",
        cron_admin_views.admin_cron_schedules_run_now,
        name="admin-cron-run-now",
    ),
]
