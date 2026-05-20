"""StreamField blocks used to compose editorial pages.

Each block has a clean, JSON-serialisable shape so the Next.js front-end can map
it to a React component. Kept deliberately small for the v1 "socle" scope; more
blocks (stat band, value grid, service grid, person tag, testimonial…) are added
when the matching collections / pages are built out.
"""
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

RICHTEXT_FEATURES = [
    "h2", "h3", "h4", "bold", "italic", "ol", "ul",
    "link", "document-link", "hr", "blockquote",
]


class HeadingBlock(blocks.StructBlock):
    eyebrow = blocks.CharBlock(required=False, label="Sur-titre (eyebrow)")
    title = blocks.CharBlock(required=True, label="Titre")
    text = blocks.RichTextBlock(required=False, features=["bold", "italic", "link"], label="Chapô")
    alignment = blocks.ChoiceBlock(
        choices=[("left", "Gauche"), ("center", "Centré")], default="left", label="Alignement",
    )

    class Meta:
        icon = "title"
        label = "Titre de section"


class RichTextSectionBlock(blocks.StructBlock):
    body = blocks.RichTextBlock(features=RICHTEXT_FEATURES, label="Contenu")

    class Meta:
        icon = "doc-full"
        label = "Texte enrichi"


class CalloutBlock(blocks.StructBlock):
    style = blocks.ChoiceBlock(
        choices=[("info", "Information (bleu)"), ("success", "Positif (vert)"), ("neutral", "Neutre")],
        default="info", label="Style",
    )
    title = blocks.CharBlock(required=False, label="Titre")
    body = blocks.RichTextBlock(features=RICHTEXT_FEATURES, label="Contenu")

    class Meta:
        icon = "help"
        label = "Encadré"


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock(label="Image")
    caption = blocks.CharBlock(required=False, label="Légende")
    alt = blocks.CharBlock(required=False, label="Texte alternatif (si différent du titre)")

    class Meta:
        icon = "image"
        label = "Image"


class QuoteBlock(blocks.StructBlock):
    quote = blocks.TextBlock(label="Citation")
    author = blocks.CharBlock(required=False, label="Auteur")
    role = blocks.CharBlock(required=False, label="Rôle / activité")

    class Meta:
        icon = "openquote"
        label = "Citation"


class CtaBandBlock(blocks.StructBlock):
    """Bandeau d'appel à l'action. Laisser vide pour réutiliser le CTA global du site."""

    use_site_default = blocks.BooleanBlock(
        required=False, default=True, label="Utiliser le bandeau « Rejoindre la coopérative » global",
    )
    title = blocks.CharBlock(required=False, label="Titre (si non global)")
    text = blocks.RichTextBlock(required=False, features=["bold", "italic", "link"], label="Texte (si non global)")
    button_label = blocks.CharBlock(required=False, label="Libellé du bouton (si non global)")
    button_page = blocks.PageChooserBlock(required=False, label="Page cible du bouton")

    class Meta:
        icon = "pick"
        label = "Bandeau d'appel à l'action"


def body_stream_block():
    """The default StreamField definition for editorial page bodies."""
    return blocks.StreamBlock(
        [
            ("heading", HeadingBlock()),
            ("rich_text", RichTextSectionBlock()),
            ("callout", CalloutBlock()),
            ("image", ImageBlock()),
            ("quote", QuoteBlock()),
            ("cta_band", CtaBandBlock()),
        ],
        use_json_field=True,
        required=False,
    )
