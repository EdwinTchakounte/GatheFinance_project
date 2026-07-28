"""URL configuration.

The site vitrine is served by a separate Next.js front-end; this Django project
exposes the Wagtail admin and a read-only headless API consumed at build/ISR time,
plus the form-submission endpoints.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from config.api import api_router


def healthcheck(_request):
    return JsonResponse({"status": "ok"})


#: Chemins publics autorises sans authentification.
#: Couvre les documents officiels de la cooperative que le portail / la
#: vitrine / le mobile doivent pouvoir afficher pour TOUS les membres
#: (et meme les visiteurs, dans certains cas) : reglement interieur PDF,
#: specimen carnet PDF, covers d'articles, flyers de campagnes, etc.
#: Tout le reste (CNI, photo identite, plan localisation, BRC...) reste
#: protege par IsStaff.
_PUBLIC_MEDIA_PREFIXES = (
    "coop/assets/",          # CooperativeAsset (reglement_interieur, carnet_specimen)
    "coop/microcampaigns/flyers/",  # Flyers de campagnes micro-credit (publics ; candidatures/ reste prive)
    "coop/blog/",            # Covers d'articles Wagtail
    "coop/announcements/",   # Visuels d'annonces broadcast
    "coop/profil/",          # Avatars de profil (le membre doit voir sa propre photo ; non-staff)
    "original_images/",      # Wagtail images (mobile/portail recoivent les URLs)
    "images/",               # Wagtail renditions
)


def protected_media(request, path):
    """Serve uploaded files derriere une autorisation staff/superuser, sauf
    pour les chemins listes dans ``_PUBLIC_MEDIA_PREFIXES`` qui restent
    publics (reglement interieur, specimen carnet, flyers de campagnes...).

    En DEBUG, l'helper django.conf.urls.static.static rend les fichiers
    publics. En prod l'image officielle backend est servie par gunicorn et
    nginx-external ne route pas /media/ -> les fichiers reviennent en 404
    visibles cote admin. Cette vue couvre les deux cas et garantit que les
    pieces d'identite restent privees, tout en exposant les documents
    officiels publics.
    """
    if any(path.startswith(prefix) for prefix in _PUBLIC_MEDIA_PREFIXES):
        return static_serve(request, path, document_root=settings.MEDIA_ROOT)
    user = request.user
    if not user.is_authenticated or not (user.is_staff or user.is_superuser):
        return HttpResponseForbidden("Pieces reservees au personnel autorise.")
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("healthz/", healthcheck, name="healthz"),
    # Admins
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    # Headless CMS API (Wagtail-backed, anonymous reads)
    path("api/v2/", api_router.urls),  # Wagtail pages / images / documents
    path("api/forms/", include("apps_cms.forms.urls")),  # contact / membership / newsletter
    path("api/site/", include("apps_cms.core.urls")),  # site settings, snippets
    # Cooperative business API (authenticated, session cookies + CSRF)
    path("api/v1/", include("config.api_v1")),
    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Serving media protege (CNI / photos / plans / BRC). Toujours actif,
    # autorise uniquement IsStaff. Session cookie partagee cross-subdomain
    # via SESSION_COOKIE_DOMAIN=.gathe-finance.horus-lab.com.
    re_path(r"^media/(?P<path>.*)$", protected_media, name="protected-media"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
    except ImportError:
        pass

# Keep Wagtail's own page-serving last so the admin can render previews/drafts.
urlpatterns += [path("", include(wagtail_urls))]
