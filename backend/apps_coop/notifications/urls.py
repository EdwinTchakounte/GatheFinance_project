"""Notifications API routes.

Mounted under ``/api/v1/notifications/`` by ``config/api_v1.py``.
"""
from django.urls import path

from . import views


app_name = "coop_notifications"

urlpatterns = [
    path("", views.list_notifications, name="list"),
    path("read-all/", views.mark_all_read, name="read-all"),
    path("<int:pk>/read/", views.mark_read, name="read"),
]
