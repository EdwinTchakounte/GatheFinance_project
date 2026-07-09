"""Wagtail page models for the GATHE Finance site.

Editorial pages are composed with the StreamField blocks in ``blocks.py`` so the
Next.js front-end can render each block as a React component. All pages are
translatable (FR default, EN secondary) via wagtail-localize.

v1 "socle" scope: HomePage, BlogIndexPage, BlogPostPage and LegalPage are wired
to the CMS. AboutPage / ServicesIndexPage / ContactPage / MembershipPage will be
added (or kept code-side) as the integration progresses — see conception/07.
"""
from django.conf import settings
from django.db import models
from django.http import HttpResponseRedirect
from modelcluster.fields import ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.api import APIField
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index

from .blocks import body_stream_block


def _absolute_media_url(url: str | None) -> str | None:
    """Rends une URL média absolue.

    Les renditions Wagtail sur un stockage fichier local renvoient un chemin
    relatif (`/media/images/…`). Consommé tel quel par l'admin Next.js
    (`admin.*`), le mobile ou le portail — tous sur un autre hôte que l'API —
    le navigateur résout `/media/…` contre le mauvais domaine → image cassée.
    On préfixe donc avec l'URL publique du backend. Les URL déjà absolues
    (stockage S3/CDN, photos stock Unsplash) sont renvoyées telles quelles.
    """
    if not url or url.startswith(("http://", "https://", "//")):
        return url
    base = (
        getattr(settings, "WAGTAILADMIN_BASE_URL", None)
        or getattr(settings, "PUBLIC_BASE_URL", None)
        or ""
    ).rstrip("/")
    return f"{base}{url}" if base else url


def _frontend_url_for(page: Page) -> str:
    """URL absolue Next.js pour une page Wagtail (locale-aware).

    Headless setup : Wagtail ne rend pas de HTML. Quand on clique sur
    "Voir sur le site" (`serve()`) ou "Aperçu" (`serve_preview()`),
    on redirige vers le front Next.js qui rend la page via l'API.

    Mapping (aligné sur ``apps_cms.cms.signals._page_paths``) :
      - locale FR (défaut) : ``{FRONTEND_BASE_URL}/<path>``
      - locale EN          : ``{FRONTEND_BASE_URL}/en/<path>``
    """
    # Appelle la méthode bound de Page (non l'override) pour éviter la récursion.
    try:
        url_path = Page.get_url_parts(page, request=None)[2]
    except Exception:  # noqa: BLE001
        url_path = "/"
    locale = getattr(getattr(page, "locale", None), "language_code", "fr")
    prefix = "" if locale == "fr" else f"/{locale}"
    path = f"{prefix}{url_path}".rstrip("/") or "/"
    base = (getattr(settings, "FRONTEND_PUBLIC_URL", None)
            or settings.FRONTEND_BASE_URL
            or "http://localhost:3000").rstrip("/")
    return f"{base}{path}"


class BasePage(Page):
    """Common SEO helpers shared by all page types.

    **Headless** : on n'a aucun template HTML côté Wagtail. Les boutons
    "Voir sur le site" et "Aperçu" sont donc redirigés vers la vitrine
    Next.js qui rend les pages depuis l'API. La méthode `serve()` Wagtail
    par défaut ferait un `get_template()` → `TemplateDoesNotExist`.
    """

    search_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Image de partage (Open Graph)",
    )

    promote_panels = Page.promote_panels + [FieldPanel("search_image")]

    api_fields = [
        APIField("seo_title"),
        APIField("search_description"),
        APIField("search_image"),
        APIField("last_published_at"),
        APIField("locale"),
    ]

    class Meta:
        abstract = True

    # ----- Headless rendering -----------------------------------------------

    def serve(self, request, *args, **kwargs):
        """Bouton 'Voir sur le site' (et accès direct à l'URL Wagtail).

        On redirige vers le rendu Next.js — l'URL canonique de l'article
        sur la vitrine publique.
        """
        return HttpResponseRedirect(_frontend_url_for(self))

    def serve_preview(self, request, mode_name):
        """Bouton 'Aperçu' dans l'admin.

        En attendant un vrai mode preview avec draftMode Next.js (S11),
        on redirige aussi vers la version publiée Next.js. L'éditeur voit
        toujours la dernière version *publiée* — il doit publier pour
        prévisualiser ses changements (les brouillons restent côté Wagtail).
        """
        return HttpResponseRedirect(_frontend_url_for(self))

    # Désactive la liste des "preview modes" → le bouton Aperçu reste utilisable
    # mais ne déclenche pas la résolution de template.
    preview_modes: list = []


class HomePage(BasePage):
    """Page d'accueil."""

    # --- Héros ---
    hero_eyebrow = models.CharField(
        "Sur-titre du héros", max_length=160, blank=True,
        default="Coopérative d'épargne et de crédit",
    )
    hero_title = models.CharField(
        "Titre du héros", max_length=200, default="Un avenir financier entre vos mains",
    )
    hero_text = RichTextField(
        "Texte du héros", blank=True,
        help_text="Ex. « Que vous démarriez une activité ou cherchiez à la développer… »",
    )
    hero_primary_label = models.CharField(
        "Libellé bouton principal", max_length=80, blank=True, default="Rejoindre la coopérative",
    )
    hero_secondary_label = models.CharField(
        "Libellé bouton secondaire", max_length=80, blank=True, default="Découvrir nos services",
    )
    hero_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Image du héros",
    )

    # --- Bloc « Qui sommes-nous » (présentation courte sur l'accueil) ---
    intro_title = models.CharField(
        "Titre du bloc présentation", max_length=200, blank=True,
        default="GATHE finance, la coopérative d'épargne et de crédit des entrepreneurs",
    )
    intro_text = RichTextField("Texte du bloc présentation", blank=True)

    # --- Contenu libre additionnel ---
    body = StreamField(body_stream_block(), blank=True, verbose_name="Sections additionnelles")

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("hero_eyebrow"),
                FieldPanel("hero_title"),
                FieldPanel("hero_text"),
                FieldPanel("hero_primary_label"),
                FieldPanel("hero_secondary_label"),
                FieldPanel("hero_image"),
            ],
            heading="Héros",
        ),
        MultiFieldPanel(
            [FieldPanel("intro_title"), FieldPanel("intro_text")],
            heading="Bloc présentation",
        ),
        FieldPanel("body"),
    ]

    api_fields = BasePage.api_fields + [
        APIField("hero_eyebrow"),
        APIField("hero_title"),
        APIField("hero_text"),
        APIField("hero_primary_label"),
        APIField("hero_secondary_label"),
        APIField("hero_image"),
        APIField("intro_title"),
        APIField("intro_text"),
        APIField("body"),
    ]

    # Only one home page per locale, placed at the site root.
    max_count_per_parent = 1
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["cms.BlogIndexPage", "cms.LegalPage"]

    class Meta:
        verbose_name = "Page d'accueil"


class LegalPage(BasePage):
    """Page éditoriale générique (mentions légales, politique de confidentialité, …)."""

    body = StreamField(body_stream_block(), blank=True, verbose_name="Contenu")

    content_panels = Page.content_panels + [FieldPanel("body")]

    api_fields = BasePage.api_fields + [APIField("body")]

    parent_page_types = ["cms.HomePage"]
    subpage_types = []

    class Meta:
        verbose_name = "Page éditoriale / légale"


class BlogIndexPage(BasePage):
    """Page liste du blog."""

    intro = RichTextField("Introduction", blank=True)

    content_panels = Page.content_panels + [FieldPanel("intro")]
    api_fields = BasePage.api_fields + [APIField("intro")]

    max_count_per_parent = 1
    parent_page_types = ["cms.HomePage"]
    subpage_types = ["cms.BlogPostPage"]

    class Meta:
        verbose_name = "Blog (liste)"


class BlogPostPage(BasePage):
    """Article de blog."""

    date = models.DateField("Date de publication")
    author = models.ForeignKey(
        "content.Author", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posts", verbose_name="Auteur",
    )
    categories = ParentalManyToManyField("content.Category", blank=True, verbose_name="Catégories")
    cover_image = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Image de couverture",
    )
    excerpt = models.TextField("Extrait", blank=True, max_length=400)
    body = StreamField(body_stream_block(), blank=True, verbose_name="Contenu de l'article")

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("date"),
                FieldPanel("author"),
                FieldPanel("categories"),
                FieldPanel("cover_image"),
                FieldPanel("excerpt"),
            ],
            heading="Métadonnées",
        ),
        FieldPanel("body"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("excerpt"),
        index.SearchField("body"),
    ]

    # --- API helpers: flat, JSON-friendly shapes for the headless front-end ---
    @property
    def author_name(self):
        return self.author.name if self.author else None

    @property
    def category_list(self):
        return [{"name": c.name, "slug": c.slug} for c in self.categories.all()]

    @property
    def cover_image_data(self):
        """Toujours retourner un dict {url, ...} : image éditeur en
        priorité, sinon photo stock Unsplash choisie d'après les mots-clés
        du titre. Source unique de vérité pour mobile / portail / admin.
        """
        if self.cover_image:
            rendition = self.cover_image.get_rendition("fill-1280x720")
            # `full_url` = URL absolue (préfixe WAGTAILADMIN_BASE_URL si le
            # stockage renvoie un chemin relatif ; renvoyée telle quelle en
            # S3/CDN). Indispensable : admin / mobile / portail consomment
            # cette URL depuis un autre hôte que l'API — un `/media/…` relatif
            # s'y résout contre le mauvais domaine → image cassée.
            return {
                "url": _absolute_media_url(rendition.full_url),
                "width": rendition.width,
                "height": rendition.height,
                "alt": self.cover_image.title,
                "source": "cms",
            }
        from apps_cms.cms.stock_images import article_image_for
        url = article_image_for(self.title)
        return {"url": _absolute_media_url(url), "width": 900, "height": 506, "alt": self.title, "source": "stock"}

    api_fields = BasePage.api_fields + [
        APIField("date"),
        APIField("author_name"),
        APIField("category_list"),
        APIField("cover_image_data"),
        APIField("excerpt"),
        APIField("body"),
    ]

    parent_page_types = ["cms.BlogIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Article de blog"
        ordering = ["-date"]
