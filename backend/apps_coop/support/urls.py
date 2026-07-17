"""Routes Support membre (montées sous /api/v1/support/)."""
from django.urls import path

from . import views


app_name = "support"

urlpatterns = [
    # Membre
    path("thread/", views.my_thread, name="my-thread"),
    path("messages/", views.post_message, name="post-message"),
    path("unread/", views.my_unread, name="my-unread"),
    # Admin / staff
    path("admin/threads/", views.admin_threads, name="admin-threads"),
    path(
        "admin/threads/<int:pk>/",
        views.admin_thread_detail,
        name="admin-thread-detail",
    ),
    path(
        "admin/threads/<int:pk>/reply/",
        views.admin_reply,
        name="admin-reply",
    ),
]
