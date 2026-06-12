"""URL conf pour le moteur FormSchema (monté sous /api/v1/forms/)."""
from django.urls import path

from . import views


urlpatterns = [
    # Public — schéma actif
    path("schemas/<str:kind>/active/", views.public_active_schema, name="form-schemas-active"),
    # Admin CRUD
    path("admin/schemas/", views.admin_schema_list, name="form-schemas-admin-list"),
    path("admin/schemas/<int:pk>/", views.admin_schema_detail, name="form-schemas-admin-detail"),
    path("admin/schemas/<int:pk>/activate/", views.admin_schema_activate, name="form-schemas-admin-activate"),
    path("admin/schemas/<int:pk>/duplicate/", views.admin_schema_duplicate, name="form-schemas-admin-duplicate"),
]
