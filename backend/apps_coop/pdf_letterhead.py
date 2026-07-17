"""Papier en-tête officiel GATHE Finance pour les PDF générés (reportlab).

Reproduit fidèlement le papier à en-tête de la coopérative (``docs/papier
entête GATHE.docx``) : logo couleur en haut, raison sociale, ligne
d'immatriculation, filet tricolore, et bandeau bleu de contacts en pied de
page. Toutes les couleurs sont celles réelles du logo (bleu vif, vert vif,
vert foncé) — plus les teintes ternes des anciens en-têtes texte.

Auto-contenu : aucune I/O réseau, le logo est lu depuis les assets locaux
(le même que le filigrane). Utilisé par tous les générateurs (reçu, note de
crédit, attestation, relevés/carnet).
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm

logger = logging.getLogger(__name__)

# --- Couleurs de marque (RÉELLES, relevées sur le logo/papier en-tête) ----
BRAND_BLUE = colors.HexColor("#0747FF")   # bleu vif du logo + bandeau pied
BRAND_GREEN = colors.HexColor("#33CC00")  # vert vif (accents, filet droit)
BRAND_GREEN_DARK = colors.HexColor("#14820E")  # vert foncé (« GAT », filet)
HEADER_BG = colors.HexColor("#F0F4F3")    # fond très clair de l'en-tête
WHITE = colors.white

# --- Identité coopérative (papier en-tête de référence) -------------------
COOP_TITLE = "SOCIÉTÉ COOPÉRATIVE D'EPARGNE ET DE CRÉDIT"
COOP_IMMAT = (
    "Immatriculée sous le N°24/046/CMR/LT/01/001/CCA/036004/036 004 000"
)
CONTACT_LINE_1 = (
    "Tél : +237 233 424 847     Mob : +237 676 887 686     "
    "Email : contact@gathe-finance.com     Web : www.gathe-finance.com"
)
CONTACT_LINE_2 = (
    "NUI : N°M062416925084G     B.P. : 7761 - Douala     "
    "Akwa - Douala Bercy (20m de Santa Lucia)"
)

_LOGO_PATH = Path(__file__).resolve().parent / "notifications" / "assets" / "logo.png"
_logo_reader = None


def _logo():
    """Charge le logo couleur une seule fois (ImageReader mémoïsé)."""
    global _logo_reader
    if _logo_reader is None:
        from reportlab.lib.utils import ImageReader

        _logo_reader = ImageReader(str(_LOGO_PATH))
    return _logo_reader


def _tricolor_rule(c, x0, x1, y, *, thickness=2.4) -> None:
    """Filet tricolore bleu / vert foncé / vert vif (comme le papier)."""
    span = x1 - x0
    # Trois segments contigus (≈ 40 / 30 / 30 % comme la référence).
    b_end = x0 + span * 0.40
    d_end = x0 + span * 0.70
    half = thickness / 2.0
    for xa, xb, col in (
        (x0, b_end, BRAND_BLUE),
        (b_end, d_end, BRAND_GREEN_DARK),
        (d_end, x1, BRAND_GREEN),
    ):
        c.setFillColor(col)
        c.rect(xa, y - half, xb - xa, thickness, stroke=0, fill=1)


def draw_header(c, width, height, *, margin) -> float:
    """Dessine l'en-tête officiel en haut de la page courante.

    Retourne l'ordonnée ``content_top`` : la première position Y utilisable
    par le contenu du document, sous le filet tricolore.
    """
    x0, x1 = margin, width - margin

    # Bandeau de fond clair derrière logo + titre.
    band_h = 34 * mm
    band_top = height - 8 * mm
    c.setFillColor(HEADER_BG)
    c.rect(x0, band_top - band_h, x1 - x0, band_h, stroke=0, fill=1)

    # Logo couleur centré.
    logo_w = 38 * mm
    logo_h = logo_w * 109.0 / 249.0  # ratio natif du PNG
    logo_y = band_top - logo_h - 2 * mm
    try:
        c.drawImage(
            _logo(),
            width / 2 - logo_w / 2,
            logo_y,
            width=logo_w,
            height=logo_h,
            mask="auto",
            preserveAspectRatio=True,
        )
    except Exception:  # best-effort : jamais bloquant
        logger.warning("Logo GATHE (en-tête) non dessiné.", exc_info=True)

    # Raison sociale.
    title_y = logo_y - 6 * mm
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(width / 2, title_y, COOP_TITLE)

    # Pilule verte d'immatriculation.
    c.setFont("Helvetica", 7.5)
    immat_w = c.stringWidth(COOP_IMMAT, "Helvetica", 7.5)
    pill_w = immat_w + 14
    pill_h = 12
    pill_y = title_y - pill_h - 3
    c.setFillColor(BRAND_GREEN_DARK)
    c.roundRect(
        width / 2 - pill_w / 2, pill_y, pill_w, pill_h, pill_h / 2, stroke=0, fill=1
    )
    c.setFillColor(WHITE)
    c.drawCentredString(width / 2, pill_y + 3.2, COOP_IMMAT)

    # Filet tricolore sous l'en-tête.
    rule_y = pill_y - 6
    _tricolor_rule(c, x0, x1, rule_y)

    return rule_y - 10 * mm


def draw_footer(c, width, *, margin) -> float:
    """Dessine le pied officiel (filet tricolore + bandeau bleu contacts).

    Retourne l'ordonnée ``content_bottom`` : la position Y minimale que le
    contenu ne doit pas franchir.
    """
    x0, x1 = margin, width - margin

    band_h = 15 * mm
    band_y = 8 * mm

    # Filet tricolore juste au-dessus du bandeau.
    _tricolor_rule(c, x0, x1, band_y + band_h + 2)

    # Bandeau bleu pleine largeur (marge à marge).
    c.setFillColor(BRAND_BLUE)
    c.rect(x0, band_y, x1 - x0, band_h, stroke=0, fill=1)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 7.6)
    c.drawCentredString(width / 2, band_y + band_h - 6, CONTACT_LINE_1)
    c.setFont("Helvetica", 7.6)
    c.drawCentredString(width / 2, band_y + 4.5, CONTACT_LINE_2)

    return band_y + band_h + 8 * mm


def draw_letterhead(c, width, height, *, margin) -> tuple[float, float]:
    """Dessine en-tête + pied sur la page courante.

    Retourne ``(content_top, content_bottom)`` — les bornes verticales de la
    zone de contenu.
    """
    content_top = draw_header(c, width, height, margin=margin)
    content_bottom = draw_footer(c, width, margin=margin)
    return content_top, content_bottom
