"""URLs de l'admin API CMS (montées sous /api/v1/cms/)."""
from django.urls import path

from . import admin_api

urlpatterns = [
    path("blog/", admin_api.blog_list, name="cms-blog-list"),
    path(
        "blog/<int:page_id>/cover-image/",
        admin_api.blog_set_cover_image,
        name="cms-blog-set-cover-image",
    ),
    path(
        "blog/<int:page_id>/live/",
        admin_api.blog_set_live,
        name="cms-blog-set-live",
    ),
    path(
        "blog/<int:page_id>/i18n/",
        admin_api.blog_i18n,
        name="cms-blog-i18n",
    ),
]
