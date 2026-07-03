"""URLs de l'admin API CMS (montées sous /api/v1/cms/)."""
from django.urls import path

from . import admin_api

urlpatterns = [
    path(
        "blog/<int:page_id>/cover-image/",
        admin_api.blog_set_cover_image,
        name="cms-blog-set-cover-image",
    ),
]
