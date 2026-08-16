"""Routes des collectes particulières (membre + admin)."""
from django.urls import path

from . import views

urlpatterns = [
    # Membre
    path("", views.my_collections, name="special-collections-mine"),
    path("request/", views.request_collection, name="special-collections-request"),
    path("transfer/", views.transfer, name="special-collections-transfer"),
    path(
        "<str:type>/transactions/",
        views.my_collection_transactions,
        name="special-collections-transactions",
    ),
    # Admin
    path("admin/", views.admin_list, name="special-collections-admin-list"),
    path("admin/<int:pk>/", views.admin_detail, name="special-collections-admin-detail"),
    path(
        "admin/<int:pk>/validate/",
        views.admin_validate,
        name="special-collections-admin-validate",
    ),
    path(
        "admin/<int:pk>/reject/",
        views.admin_reject,
        name="special-collections-admin-reject",
    ),
]
