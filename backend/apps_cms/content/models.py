"""Reusable, non-page content (Wagtail snippets).

Maps to the "COLLECTION" content category of conception/07. For the v1 "socle"
scope, only blog-related snippets (Category, Author) and KeyFigure are wired;
Service / ServiceItem / Value / TeamMember / Agency / Testimonial / Faq / Partner
will be added when the optional collections (Lot 2) are activated.
"""
from django.db import models
from django.utils.text import slugify
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import TranslatableMixin
from wagtail.search import index
from wagtail.snippets.models import register_snippet


@register_snippet
class Category(TranslatableMixin, index.Indexed, models.Model):
    """Catégorie d'article de blog (ex. « Conseils »)."""

    name = models.CharField("Nom", max_length=120)
    slug = models.SlugField("Slug", max_length=140, allow_unicode=True)
    description = models.CharField("Description courte", max_length=255, blank=True)

    panels = [FieldPanel("name"), FieldPanel("slug"), FieldPanel("description")]

    search_fields = [index.SearchField("name")]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]


@register_snippet
class Author(TranslatableMixin, index.Indexed, models.Model):
    """Auteur d'article (ex. « GATHE »)."""

    name = models.CharField("Nom", max_length=160)
    role = models.CharField("Fonction / rôle", max_length=160, blank=True)
    bio = RichTextField("Bio courte", blank=True)
    photo = models.ForeignKey(
        "wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", verbose_name="Photo",
    )
    link = models.URLField("Lien (site, profil…)", blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("role"),
        FieldPanel("bio"),
        FieldPanel("photo"),
        FieldPanel("link"),
    ]

    search_fields = [index.SearchField("name"), index.SearchField("role")]

    def __str__(self):
        return self.name

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Auteur"
        verbose_name_plural = "Auteurs"
        ordering = ["name"]


@register_snippet
class KeyFigure(TranslatableMixin, index.Indexed, models.Model):
    """Chiffre clé (ex. « 4 500 projets financés », « 400 M FCFA financés »)."""

    value = models.CharField("Valeur (ex. 4 500, 400)", max_length=40)
    suffix = models.CharField("Suffixe (ex. « M FCFA », « + »)", max_length=40, blank=True)
    label = models.CharField("Libellé", max_length=160)
    sort_order = models.PositiveIntegerField("Ordre", default=0)

    panels = [
        FieldPanel("value"),
        FieldPanel("suffix"),
        FieldPanel("label"),
        FieldPanel("sort_order"),
    ]

    search_fields = [index.SearchField("label")]

    def __str__(self):
        return f"{self.value}{self.suffix} — {self.label}"

    class Meta(TranslatableMixin.Meta):
        verbose_name = "Chiffre clé"
        verbose_name_plural = "Chiffres clés"
        ordering = ["sort_order", "id"]
