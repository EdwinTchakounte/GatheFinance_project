"""Site-wide settings (singletons) exposed to the front-end.

These map to the "CONFIG" content category of conception/07: coordinates,
opening hours, social links, the global CTA band, and default SEO/PWA values.
Editable by the client in the Wagtail admin under "Settings".
"""
from django.db import models
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.fields import RichTextField


@register_setting(icon="cog")
class SiteSettings(BaseGenericSetting):
    """Coordonnées, réseaux sociaux et bandeau d'appel à l'action."""

    # --- Coordonnées (siège) ---
    legal_name = models.CharField(
        "Raison sociale", max_length=255, default="Gathe Finance"
    )
    baseline = models.CharField(
        "Baseline", max_length=255, blank=True,
        default="Coopérative d'épargne et de crédit au Cameroun",
    )
    address = models.CharField(
        "Adresse du siège", max_length=255, blank=True,
        default="Rue Mermoz, Akwa, Douala, Cameroun",
    )
    phone = models.CharField("Téléphone", max_length=40, blank=True, default="+237 6 56 13 06 72")
    landline = models.CharField("Fixe", max_length=40, blank=True, default="233 42 48 47")
    email = models.EmailField("E-mail public", blank=True, default="contact@gathe-finance.com")
    opening_hours = models.CharField(
        "Heures d'ouverture (affichage)", max_length=255, blank=True,
        default="Lundi – Vendredi : 8h00 à 17h",
    )
    latitude = models.FloatField("Latitude (siège)", null=True, blank=True)
    longitude = models.FloatField("Longitude (siège)", null=True, blank=True)

    # --- Réseaux sociaux ---
    facebook_url = models.URLField("Facebook", blank=True, default="https://www.facebook.com/Gathe237")
    linkedin_url = models.URLField("LinkedIn", blank=True, default="https://www.linkedin.com/company/gathe237/")
    whatsapp_number = models.CharField(
        "Numéro WhatsApp (format international, sans +)", max_length=20, blank=True
    )

    # --- Bandeau CTA global ("Rejoindre notre coopérative…") ---
    cta_title = models.CharField(
        "Titre du bandeau CTA", max_length=255, blank=True,
        default="Rejoindre notre coopérative de crédit et d'épargne",
    )
    cta_text = RichTextField("Texte du bandeau CTA", blank=True)
    cta_button_label = models.CharField(
        "Libellé du bouton CTA", max_length=80, blank=True, default="Rejoignez la Coopérative",
    )

    # --- Pied de page ---
    copyright_text = models.CharField(
        "Mention de copyright", max_length=255, blank=True,
        default="Gathe Finance – Coopérative d'épargne et de crédit au Cameroun",
    )

    panels = [
        MultiFieldPanel(
            [
                FieldPanel("legal_name"),
                FieldPanel("baseline"),
                FieldPanel("address"),
                FieldPanel("phone"),
                FieldPanel("landline"),
                FieldPanel("email"),
                FieldPanel("opening_hours"),
                FieldPanel("latitude"),
                FieldPanel("longitude"),
            ],
            heading="Coordonnées",
        ),
        MultiFieldPanel(
            [
                FieldPanel("facebook_url"),
                FieldPanel("linkedin_url"),
                FieldPanel("whatsapp_number"),
            ],
            heading="Réseaux sociaux",
        ),
        MultiFieldPanel(
            [
                FieldPanel("cta_title"),
                FieldPanel("cta_text"),
                FieldPanel("cta_button_label"),
            ],
            heading="Bandeau « Rejoindre la coopérative »",
        ),
        FieldPanel("copyright_text"),
    ]

    class Meta:
        verbose_name = "Coordonnées & contenus globaux"


@register_setting(icon="search")
class SeoSettings(BaseGenericSetting):
    """Valeurs SEO / réseaux sociaux / PWA par défaut."""

    default_title = models.CharField(
        "Titre par défaut", max_length=255, blank=True,
        default="Gathe Finance — Coopérative d'épargne et de crédit",
    )
    default_description = models.CharField(
        "Description par défaut", max_length=300, blank=True,
        default=(
            "Coopérative d'épargne et de crédit des entrepreneurs camerounais : "
            "crédit, épargne, transferts, investissement communautaire et éducation financière."
        ),
    )
    og_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Image de partage par défaut (1200×630)",
    )
    google_site_verification = models.CharField(
        "Google Search Console (jeton de vérification)", max_length=255, blank=True
    )
    bing_site_verification = models.CharField(
        "Bing Webmaster (jeton de vérification)", max_length=255, blank=True
    )
    plausible_domain = models.CharField(
        "Domaine Plausible (analytics)", max_length=255, blank=True
    )
    ga4_measurement_id = models.CharField(
        "GA4 Measurement ID (si utilisé)", max_length=40, blank=True
    )

    panels = [
        FieldPanel("default_title"),
        FieldPanel("default_description"),
        FieldPanel("og_image"),
        MultiFieldPanel(
            [
                FieldPanel("google_site_verification"),
                FieldPanel("bing_site_verification"),
            ],
            heading="Vérification moteurs de recherche",
        ),
        MultiFieldPanel(
            [
                FieldPanel("plausible_domain"),
                FieldPanel("ga4_measurement_id"),
            ],
            heading="Analytics",
        ),
    ]

    class Meta:
        verbose_name = "SEO & analytics"
