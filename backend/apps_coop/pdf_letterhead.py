"""Papier en-tête officiel GATHE Finance pour les PDF générés (reportlab).

Reproduit fidèlement le papier à en-tête de la coopérative (``docs/papier
entête GATHE.docx``) — mais **net** (le docx d'origine est flou) : logo couleur
centré, raison sociale en gras, pastille d'immatriculation, filet tricolore
pleine largeur, et bandeau bleu de contacts **pleine largeur** avec icônes en
pied de page.

Couleurs RÉELLES relevées sur la référence (source de vérité) :
    bleu logo #004CA4 · vert foncé logo #13820E · fond gris #F0F4F3.
    (Plus aucun bleu vif ni vert vif — décision cliente.)

Auto-contenu : aucune I/O réseau, le logo est lu depuis les assets locaux
(le même que le filigrane). Utilisé par tous les générateurs (reçu, note de
crédit, attestation, relevés/carnet). Les bandes vont **de bord à bord** de la
page (pas en retrait des marges).
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm

logger = logging.getLogger(__name__)

# --- Couleurs de marque (RÉELLES, relevées PIL sur le papier en-tête) -----
BRAND_BLUE = colors.HexColor("#004CA4")        # bleu du logo + bandeau pied
BRAND_GREEN = colors.HexColor("#13820E")       # vert foncé du logo (plus de vif)
BRAND_GREEN_DARK = colors.HexColor("#13820E")  # vert foncé (segment central)
PILL_GREEN = colors.HexColor("#13820E")        # pastille immatriculation (vert foncé)
HEADER_BG = colors.HexColor("#F0F4F3")         # fond très clair de l'en-tête
WHITE = colors.white

# --- Identité coopérative (papier en-tête de référence) -------------------
COOP_TITLE = "SOCIÉTÉ COOPÉRATIVE D'EPARGNE ET DE CRÉDIT"
COOP_IMMAT = (
    "IMATRICULÉE SOUS LE N°24/046/CMR/LT/01/001/CCA/036004/036 004 000"
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


# =========================================================================
#  Filet tricolore (bande de transition dégradée) — PLEINE LARGEUR
# =========================================================================
def _tricolor_rule(c, x0, x1, y, *, thickness=3.0) -> None:
    """Bande de transition bleu / vert foncé / vert vif (≈ 40/30/30 %)."""
    span = x1 - x0
    b_end = x0 + span * 0.40
    d_end = x0 + span * 0.70
    for xa, xb, col in (
        (x0, b_end, BRAND_BLUE),
        (b_end, d_end, BRAND_GREEN_DARK),
        (d_end, x1, BRAND_GREEN),
    ):
        c.setFillColor(col)
        c.rect(xa, y, xb - xa, thickness, stroke=0, fill=1)


# =========================================================================
#  Icônes vectorielles blanches (footer) — dessinées, donc nettes
# =========================================================================
def _prep_stroke(c, w=0.9) -> None:
    c.setStrokeColor(WHITE)
    c.setLineWidth(w)
    c.setLineCap(1)
    c.setLineJoin(1)


def _icon_phone(c, cx, cy, s) -> None:
    """Smartphone : corps arrondi + haut-parleur + bouton."""
    _prep_stroke(c)
    w, h = s * 0.60, s
    c.roundRect(cx - w / 2, cy - h / 2, w, h, s * 0.12, stroke=1, fill=0)
    c.line(cx - w * 0.16, cy + h * 0.33, cx + w * 0.16, cy + h * 0.33)
    c.setFillColor(WHITE)
    c.circle(cx, cy - h * 0.32, s * 0.055, stroke=0, fill=1)


def _icon_mail(c, cx, cy, s) -> None:
    """Enveloppe : rectangle + rabat en V."""
    _prep_stroke(c)
    w, h = s * 1.18, s * 0.80
    c.rect(cx - w / 2, cy - h / 2, w, h, stroke=1, fill=0)
    c.line(cx - w / 2, cy + h / 2, cx, cy - h * 0.04)
    c.line(cx + w / 2, cy + h / 2, cx, cy - h * 0.04)


def _icon_globe(c, cx, cy, s) -> None:
    """Globe : cercle + méridien + équateur."""
    _prep_stroke(c)
    r = s * 0.5
    c.circle(cx, cy, r, stroke=1, fill=0)
    c.ellipse(cx - r * 0.46, cy - r, cx + r * 0.46, cy + r, stroke=1, fill=0)
    c.line(cx - r, cy, cx + r, cy)


def _icon_pin(c, cx, cy, s) -> None:
    """Épingle de localisation (goutte pleine + trou)."""
    r = s * 0.34
    top = cy + s * 0.16
    c.setFillColor(WHITE)
    c.circle(cx, top, r, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(cx - r * 0.92, top - r * 0.30)
    p.lineTo(cx + r * 0.92, top - r * 0.30)
    p.lineTo(cx, cy - s * 0.5)
    p.close()
    c.drawPath(p, stroke=0, fill=1)
    c.setFillColor(BRAND_BLUE)  # trou = couleur du bandeau
    c.circle(cx, top, r * 0.42, stroke=0, fill=1)
    c.setFillColor(WHITE)


# =========================================================================
#  En-tête
# =========================================================================
def draw_header(c, width, height, *, margin) -> float:
    """Dessine l'en-tête officiel (bande pleine largeur) en haut de la page.

    Retourne ``content_top`` : première ordonnée utilisable par le contenu,
    sous le filet tricolore.
    """
    top = height

    # --- Géométrie verticale (calculée avant de peindre le fond) ----------
    logo_top = top - 7 * mm
    logo_w = 44 * mm
    logo_h = logo_w * 109.0 / 249.0
    logo_bottom = logo_top - logo_h

    # Titre : gras, auto-ajusté pour tenir la largeur utile.
    title_size = 16.0
    while (
        c.stringWidth(COOP_TITLE, "Helvetica-Bold", title_size) > width - 30
        and title_size > 10
    ):
        title_size -= 0.5
    title_baseline = logo_bottom - 5.2 * mm

    pill_size = 8.0
    pill_h = 13.0
    pill_top = title_baseline - 3.6 * mm
    pill_bottom = pill_top - pill_h

    rule_thick = 3.0
    rule_y = pill_bottom - 3.4 * mm
    band_bottom = rule_y - 2.2 * mm

    # --- Fond gris pleine largeur (derrière logo + titre) -----------------
    c.setFillColor(HEADER_BG)
    c.rect(0, band_bottom, width, top - band_bottom, stroke=0, fill=1)

    # --- Logo couleur centré ----------------------------------------------
    try:
        c.drawImage(
            _logo(),
            width / 2 - logo_w / 2,
            logo_bottom,
            width=logo_w,
            height=logo_h,
            mask="auto",
            preserveAspectRatio=True,
        )
    except Exception:  # best-effort : jamais bloquant
        logger.warning("Logo GATHE (en-tête) non dessiné.", exc_info=True)

    # --- Raison sociale (GRAS, bleu logo) ---------------------------------
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", title_size)
    c.drawCentredString(width / 2, title_baseline, COOP_TITLE)

    # --- Pastille verte d'immatriculation (texte blanc) -------------------
    c.setFont("Helvetica-Bold", pill_size)
    immat_w = c.stringWidth(COOP_IMMAT, "Helvetica-Bold", pill_size)
    pill_w = immat_w + 20
    c.setFillColor(PILL_GREEN)
    c.roundRect(
        width / 2 - pill_w / 2, pill_bottom, pill_w, pill_h,
        pill_h / 2, stroke=0, fill=1,
    )
    c.setFillColor(WHITE)
    c.drawCentredString(width / 2, pill_bottom + 3.4, COOP_IMMAT)

    # --- Filet tricolore pleine largeur -----------------------------------
    _tricolor_rule(c, 0, width, rule_y, thickness=rule_thick)

    return band_bottom - 9 * mm


# =========================================================================
#  Pied de page
# =========================================================================
def _footer_row(c, items, cy, x_left, x_right, *, font, size, icon_size) -> None:
    """Dispose une rangée d'items ``(icone|None, texte)`` justifiée en largeur."""
    gap = 3.2  # espace icône → texte

    widths = []
    for icon_fn, text in items:
        tw = c.stringWidth(text, font, size)
        widths.append((icon_size + gap if icon_fn else 0) + tw)

    total = sum(widths)
    n = len(items)
    between = (x_right - x_left - total) / (n - 1) if n > 1 else 0
    if between < 6:
        between = 6

    x = x_left
    for (icon_fn, text), iw in zip(items, widths):
        if icon_fn:
            icon_fn(c, x + icon_size / 2, cy, icon_size)
            tx = x + icon_size + gap
        else:
            tx = x
        c.setFillColor(WHITE)
        c.setFont(font, size)
        c.drawString(tx, cy - size * 0.34, text)
        x += iw + between


def draw_footer(c, width, *, margin) -> float:
    """Dessine le pied officiel PLEINE LARGEUR (filet tricolore + bandeau bleu).

    Retourne ``content_bottom`` : ordonnée minimale à ne pas franchir.
    """
    band_h = 17 * mm

    # Filet tricolore pleine largeur juste au-dessus du bandeau.
    _tricolor_rule(c, 0, width, band_h + 1.5, thickness=3.0)

    # Bandeau bleu pleine largeur (bord à bord, jusqu'au bas de page).
    c.setFillColor(BRAND_BLUE)
    c.rect(0, 0, width, band_h, stroke=0, fill=1)

    x_left, x_right = 16, width - 16
    row1 = [
        (_icon_phone, "+237 233 424 847"),
        (_icon_phone, "+237 676 887 686"),
        (_icon_mail, "contact@gathe-finance.com"),
        (_icon_globe, "www.gathe-finance.com"),
    ]
    row2 = [
        (None, "NUI : N°M062416925084G"),
        (None, "B.P. : 7761 - Douala"),
        (_icon_pin, "Akwa - Douala Bercy (20m de Santa Lucia)"),
    ]
    _footer_row(
        c, row1, band_h * 0.66, x_left, x_right,
        font="Helvetica-Bold", size=7.6, icon_size=9.5,
    )
    _footer_row(
        c, row2, band_h * 0.28, x_left, x_right,
        font="Helvetica", size=7.6, icon_size=9.5,
    )

    return band_h + 8 * mm


def draw_letterhead(c, width, height, *, margin) -> tuple[float, float]:
    """Dessine en-tête + pied sur la page courante.

    Retourne ``(content_top, content_bottom)`` — bornes verticales du contenu.
    """
    content_top = draw_header(c, width, height, margin=margin)
    content_bottom = draw_footer(c, width, margin=margin)
    return content_top, content_bottom
