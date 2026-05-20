"""Read-only JSON endpoints for site-wide settings and public snippets.

Consumed by the Next.js front-end at build / ISR-revalidation time.
"""
from django.http import JsonResponse
from wagtail.images.models import Image

from .models import SeoSettings, SiteSettings


def _image_payload(image: Image | None):
    if not image:
        return None
    rendition = image.get_rendition("width-1200")
    return {
        "id": image.pk,
        "title": image.title,
        "url": rendition.url,
        "width": rendition.width,
        "height": rendition.height,
        "alt": image.title,
    }


def site_settings(request):
    site = SiteSettings.load(request_or_site=request)
    seo = SeoSettings.load(request_or_site=request)
    return JsonResponse(
        {
            "legalName": site.legal_name,
            "baseline": site.baseline,
            "address": site.address,
            "phone": site.phone,
            "landline": site.landline,
            "email": site.email,
            "openingHours": site.opening_hours,
            "geo": (
                {"lat": site.latitude, "lng": site.longitude}
                if site.latitude is not None and site.longitude is not None
                else None
            ),
            "social": {
                "facebook": site.facebook_url or None,
                "linkedin": site.linkedin_url or None,
                "whatsapp": site.whatsapp_number or None,
            },
            "cta": {
                "title": site.cta_title,
                "text": site.cta_text,
                "buttonLabel": site.cta_button_label,
            },
            "copyright": site.copyright_text,
            "seo": {
                "defaultTitle": seo.default_title,
                "defaultDescription": seo.default_description,
                "ogImage": _image_payload(seo.og_image),
                "googleSiteVerification": seo.google_site_verification or None,
                "bingSiteVerification": seo.bing_site_verification or None,
                "plausibleDomain": seo.plausible_domain or None,
                "ga4MeasurementId": seo.ga4_measurement_id or None,
            },
        }
    )
