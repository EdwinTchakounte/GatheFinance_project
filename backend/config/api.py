"""Wagtail headless API (v2).

Exposed at /api/v2/. Used by the Next.js front-end at build / ISR-revalidation
time only (never per visitor request).

We subclass each viewset to pin `permission_classes = [AllowAny]` explicitly:
the project-level DRF default is now `IsAuthenticated` (for the cooperative
API) and would otherwise lock the public CMS API behind a login.
"""
from rest_framework.permissions import AllowAny

from wagtail.api.v2.router import WagtailAPIRouter
from wagtail.api.v2.views import PagesAPIViewSet
from wagtail.documents.api.v2.views import DocumentsAPIViewSet
from wagtail.images.api.v2.views import ImagesAPIViewSet


class PublicPagesAPIViewSet(PagesAPIViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []


class PublicImagesAPIViewSet(ImagesAPIViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []


class PublicDocumentsAPIViewSet(DocumentsAPIViewSet):
    permission_classes = [AllowAny]
    authentication_classes: list = []


api_router = WagtailAPIRouter("wagtailapi")
api_router.register_endpoint("pages", PublicPagesAPIViewSet)
api_router.register_endpoint("images", PublicImagesAPIViewSet)
api_router.register_endpoint("documents", PublicDocumentsAPIViewSet)
