"""Routes API interactions sociales — montees sous /api/v1/social/."""
from __future__ import annotations

from django.urls import path

from . import views


app_name = "coop_social"


# On wrap les vues "kind libre" en injectant `kind` figeable par URL pour
# garder des chemins parlants ("/articles/" vs "/campaigns/") tout en
# reutilisant la meme implementation interne.
def _bind_kind(view, kind: str):
    def _wrapped(request, *args, **kwargs):
        return view(request, kind=kind, *args, **kwargs)

    _wrapped.__name__ = f"{view.__name__}_{kind}"
    _wrapped.__doc__ = view.__doc__
    return _wrapped


urlpatterns = [
    # --- Articles (BlogPostPage) -------------------------------------------
    path(
        "articles/<int:object_id>/like/",
        _bind_kind(views.toggle_like, "article"),
        name="article-like",
    ),
    path(
        "articles/<int:object_id>/reaction/",
        _bind_kind(views.get_reaction, "article"),
        name="article-reaction",
    ),
    path(
        "articles/<int:object_id>/comments/",
        _bind_kind(views.comments_for_target, "article"),
        name="article-comments",
    ),
    # --- Campagnes (MicrocreditCampaign) -----------------------------------
    path(
        "campaigns/<int:object_id>/like/",
        _bind_kind(views.toggle_like, "campaign"),
        name="campaign-like",
    ),
    path(
        "campaigns/<int:object_id>/reaction/",
        _bind_kind(views.get_reaction, "campaign"),
        name="campaign-reaction",
    ),
    path(
        "campaigns/<int:object_id>/comments/",
        _bind_kind(views.comments_for_target, "campaign"),
        name="campaign-comments",
    ),
    # --- Suppression par l'auteur ------------------------------------------
    path(
        "comments/<int:pk>/",
        views.delete_my_comment,
        name="delete-my-comment",
    ),
    # --- Admin --------------------------------------------------------------
    path(
        "admin/comments/",
        views.admin_comments_list,
        name="admin-comments-list",
    ),
    path(
        "admin/comments/<int:pk>/hide/",
        views.admin_hide_comment,
        name="admin-comments-hide",
    ),
    path(
        "admin/comments/<int:pk>/unhide/",
        views.admin_unhide_comment,
        name="admin-comments-unhide",
    ),
]
