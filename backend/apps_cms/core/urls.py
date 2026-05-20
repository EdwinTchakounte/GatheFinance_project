from django.urls import path

from . import views

app_name = "core_api"

urlpatterns = [
    path("settings/", views.site_settings, name="settings"),
]
