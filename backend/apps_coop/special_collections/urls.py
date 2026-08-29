"""Routes des collectes particulières (membre + admin + cycles + groupes)."""
from django.urls import path

from . import group_views, views

urlpatterns = [
    # Membre
    path("", views.my_collections, name="special-collections-mine"),
    path("request/", views.request_collection, name="special-collections-request"),
    path("transfer/", views.transfer, name="special-collections-transfer"),
    # Tontines de GROUPE — membre / rôles (AVANT <str:type>/transactions/)
    path("groups/", group_views.my_groups, name="group-tontines-mine"),
    path("groups/<int:pk>/", group_views.group_detail, name="group-tontine-detail"),
    path("groups/<int:pk>/payout/", group_views.group_payout, name="group-tontine-payout"),
    path("groups/<int:pk>/loan/", group_views.group_loan, name="group-tontine-loan"),
    path(
        "groups/<int:pk>/loan/<int:loan_id>/repay/",
        group_views.group_loan_repay,
        name="group-tontine-loan-repay",
    ),
    path("groups/<int:pk>/role/", group_views.group_set_role, name="group-tontine-role"),
    # Rôles personnalisés (actions rattachées) — membre habilité « gérer le roster ».
    path("groups/<int:pk>/roles/", group_views.group_roles, name="group-tontine-roles"),
    path(
        "groups/<int:pk>/roles/<int:role_id>/",
        group_views.group_role_detail,
        name="group-tontine-role-detail",
    ),
    path(
        "groups/<int:pk>/assign-role/",
        group_views.group_assign_role,
        name="group-tontine-assign-role",
    ),
    path(
        "groups/<int:pk>/cotiser/",
        group_views.group_transfer_cotisation,
        name="group-tontine-cotiser",
    ),
    path("groups/<int:pk>/close/", group_views.group_close, name="group-tontine-close"),
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
    path(
        "admin/<int:pk>/decaisser/",
        views.admin_decaisser,
        name="special-collections-admin-decaisser",
    ),
    # Admin — tontines de GROUPE
    path("admin/groups/", group_views.admin_groups, name="group-tontines-admin"),
    path(
        "admin/groups/<int:pk>/",
        group_views.admin_group_detail,
        name="group-tontine-admin-detail",
    ),
    path(
        "admin/groups/<int:pk>/members/add/",
        group_views.admin_group_add_member,
        name="group-tontine-admin-add-member",
    ),
    path(
        "admin/groups/<int:pk>/members/remove/",
        group_views.admin_group_remove_member,
        name="group-tontine-admin-remove-member",
    ),
    path(
        "admin/groups/<int:pk>/role/",
        group_views.admin_group_set_role,
        name="group-tontine-admin-role",
    ),
    path(
        "admin/groups/<int:pk>/close/",
        group_views.admin_group_close,
        name="group-tontine-admin-close",
    ),
    # Admin — rôles personnalisés.
    path(
        "admin/groups/<int:pk>/roles/",
        group_views.admin_group_roles,
        name="group-tontine-admin-roles",
    ),
    path(
        "admin/groups/<int:pk>/roles/<int:role_id>/",
        group_views.admin_group_role_detail,
        name="group-tontine-admin-role-detail",
    ),
    path(
        "admin/groups/<int:pk>/assign-role/",
        group_views.admin_group_assign_role,
        name="group-tontine-admin-assign-role",
    ),
]
