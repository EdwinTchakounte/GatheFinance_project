from django.urls import path

from . import auth_views, views

app_name = "coop_members"

urlpatterns = [
    # Auth (session cookies + CSRF)
    path("auth/csrf/", auth_views.csrf_prime, name="auth-csrf"),
    path("auth/login/", auth_views.login_view, name="auth-login"),
    path("auth/logout/", auth_views.logout_view, name="auth-logout"),
    path("auth/me/", auth_views.me_view, name="auth-me"),
    path("auth/change-password/", auth_views.change_password, name="auth-change-password"),
    # Mot de passe oublié — flow OTP par e-mail (mobile + portail).
    path(
        "auth/password-reset/request/",
        auth_views.request_password_reset,
        name="auth-password-reset-request",
    ),
    path(
        "auth/password-reset/confirm/",
        auth_views.confirm_password_reset,
        name="auth-password-reset-confirm",
    ),

    # Member self-service
    path("members/me/", views.MemberMeView.as_view(), name="member-me"),
    path("booklet/me/", views.booklet_orders_me, name="booklet-me"),
    # Typeahead picker avaliste (§7.2)
    path(
        "members/search-avaliste/",
        views.search_eligible_avalistes,
        name="members-search-avaliste",
    ),

    # Admin endpoints (Next.js admin dashboard)
    path("admin/dashboard/", views.admin_dashboard_kpis, name="admin-dashboard"),
    path("admin/members/", views.admin_list_members, name="admin-members-list"),
    path("admin/membership-requests/", views.admin_list_membership_requests, name="admin-membership-list"),
    path("admin/membership-requests/<int:pk>/interview/", views.admin_record_interview, name="admin-membership-interview"),
    path("admin/membership-requests/<int:pk>/approve/", views.admin_approve_membership_request, name="admin-membership-approve"),
    path("admin/membership-requests/<int:pk>/reject/", views.admin_reject_membership_request, name="admin-membership-reject"),

    # A2 — Réinscription annuelle (alerte douce + acte admin).
    path(
        "admin/members/<int:pk>/reinscription/confirm/",
        views.admin_confirm_member_reinscription,
        name="admin-member-reinscription-confirm",
    ),

    # LOT 1 (refonte 2026) — BRC justificatifs (membre upload, admin valide/rejette).
    path("members/me/brc/", views.brc_documents_me, name="brc-me"),
    path("admin/brc/", views.admin_list_brc_documents, name="admin-brc-list"),
    path(
        "admin/brc/<int:pk>/validate/",
        views.admin_validate_brc_document,
        name="admin-brc-validate",
    ),
    path(
        "admin/brc/<int:pk>/reject/",
        views.admin_reject_brc_document,
        name="admin-brc-reject",
    ),

    # Admin booklet . pilotage workflow payee . en_impression . delivree.
    path("admin/booklet-orders/", views.admin_list_booklet_orders, name="admin-booklet-list"),
    path(
        "admin/booklet-orders/<int:pk>/mark-printing/",
        views.admin_booklet_mark_printing,
        name="admin-booklet-mark-printing",
    ),
    path(
        "admin/booklet-orders/<int:pk>/mark-delivered/",
        views.admin_booklet_mark_delivered,
        name="admin-booklet-mark-delivered",
    ),
    path(
        "admin/booklet-orders/<int:pk>/notes/",
        views.admin_booklet_update_notes,
        name="admin-booklet-notes",
    ),
]
