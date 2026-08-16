"""Routes des collectes particulières (membre + admin + cycles)."""
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
    # Admin — cycles (AVANT les routes <int:pk> pour éviter la capture)
    path("admin/cycles/", views.admin_cycles, name="special-collections-admin-cycles"),
    path(
        "admin/cycles/<int:pk>/",
        views.admin_cycle_detail,
        name="special-collections-admin-cycle-detail",
    ),
    path(
        "admin/cycles/<int:pk>/close/",
        views.admin_cycle_close,
        name="special-collections-admin-cycle-close",
    ),
    # Admin — participations
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
