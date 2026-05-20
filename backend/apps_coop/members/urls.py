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

    # Member self-service
    path("members/me/", views.MemberMeView.as_view(), name="member-me"),
    path("booklet/me/", views.booklet_orders_me, name="booklet-me"),

    # Admin endpoints (Next.js admin dashboard)
    path("admin/dashboard/", views.admin_dashboard_kpis, name="admin-dashboard"),
    path("admin/members/", views.admin_list_members, name="admin-members-list"),
    path("admin/membership-requests/", views.admin_list_membership_requests, name="admin-membership-list"),
    path("admin/membership-requests/<int:pk>/interview/", views.admin_record_interview, name="admin-membership-interview"),
    path("admin/membership-requests/<int:pk>/approve/", views.admin_approve_membership_request, name="admin-membership-approve"),
    path("admin/membership-requests/<int:pk>/reject/", views.admin_reject_membership_request, name="admin-membership-reject"),
]
