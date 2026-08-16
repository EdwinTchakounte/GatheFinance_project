from django.urls import path

from . import auth_views, staff_views, views

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
    # PWD Option B — Setup mot de passe initial (lien e-mail welcome, 72h).
    path(
        "auth/setup-password/verify/",
        auth_views.verify_password_setup_token,
        name="auth-setup-password-verify",
    ),
    path(
        "auth/setup-password/confirm/",
        auth_views.confirm_password_setup,
        name="auth-setup-password-confirm",
    ),

    # Member self-service
    path("members/me/", views.MemberMeView.as_view(), name="member-me"),
    # D3 . Statut renouvellement annuel (banniere mobile + portail).
    path("members/me/renewal-status/", views.renewal_status_me, name="renewal-status-me"),
    path("booklet/me/", views.booklet_orders_me, name="booklet-me"),
    # Typeahead picker avaliste (§7.2)
    path(
        "members/search-avaliste/",
        views.search_eligible_avalistes,
        name="members-search-avaliste",
    ),

    # Admin endpoints (Next.js admin dashboard)
    path("admin/dashboard/", views.admin_dashboard_kpis, name="admin-dashboard"),
    # Rapports PDF — photo coop (ressource dashboard) + relevé membre (ressource
    # members, mappée par le catch-all admin/members/). La route report AVANT
    # admin/members/ pour la lisibilité ; l'ordre n'importe pas (chemins distincts).
    path("admin/report/coop/", views.admin_coop_report_pdf, name="admin-report-coop"),
    path(
        "admin/members/<int:pk>/statement/",
        views.admin_member_statement_pdf,
        name="admin-member-statement",
    ),
    path(
        "admin/members/<int:pk>/adhesion/",
        views.admin_member_adhesion,
        name="admin-member-adhesion",
    ),
    # Frais membre (adhésion / inscription) — statut + paiement depuis le compte.
    path("me/fees/", views.my_membership_fees, name="my-membership-fees"),
    path(
        "me/fees/<str:code>/pay-from-savings/",
        views.pay_membership_fee,
        name="pay-membership-fee",
    ),
    path("admin/members/", views.admin_list_members, name="admin-members-list"),
    # M1 — Création d'un membre depuis le dashboard (IsAdmin, mail mot de passe + pièces).
    path("admin/members/create/", views.admin_create_member, name="admin-member-create"),
    # « Suppression » = radiation (soft-delete) : statut RADIE + login bloqué.
    path(
        "admin/members/<int:pk>/delete/",
        views.admin_delete_member,
        name="admin-member-delete",
    ),
    path(
        "admin/members/<int:pk>/restore/",
        views.admin_restore_member,
        name="admin-member-restore",
    ),
    path("admin/membership-requests/", views.admin_list_membership_requests, name="admin-membership-list"),
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

    # Pipeline adhesion . funnel KPIs + membres suspendus avec progression
    # paiement (1/3, 2/3, 3/3 des frais d'adhesion).
    path("admin/adhesions/pipeline/", views.admin_adhesion_pipeline, name="admin-adhesions-pipeline"),

    # RBAC — Utilisateurs & accès (gestion staff + rôles/ressources).
    path("admin/access/resources/", staff_views.access_resources, name="admin-access-resources"),
    path("admin/access/roles/", staff_views.access_roles, name="admin-access-roles"),
    path("admin/access/roles/<int:pk>/", staff_views.access_role_detail, name="admin-access-role-detail"),
    path("admin/access/users/", staff_views.access_users, name="admin-access-users"),
    path("admin/access/users/<int:pk>/", staff_views.access_user_detail, name="admin-access-user-detail"),
]
