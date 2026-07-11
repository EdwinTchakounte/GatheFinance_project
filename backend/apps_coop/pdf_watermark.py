"""Filigrane logo GATHE pour les documents PDF générés (reportlab).

Dessine le logo de la coopérative, très pâle et centré, DERRIÈRE le contenu de
chaque page. À appeler juste après la création du canvas (avant tout contenu).

Best-effort : ne lève jamais d'exception — un document sans filigrane vaut
mieux qu'une génération PDF cassée.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Logo partagé (même asset que les e-mails).
_LOGO_PATH = (
    Path(__file__).resolve().parent / "notifications" / "assets" / "logo.png"
)
_logo_reader = None


def _logo():
    """ImageReader mis en cache (chargé une seule fois)."""
    global _logo_reader
    if _logo_reader is None:
        from reportlab.lib.utils import ImageReader

        _logo_reader = ImageReader(str(_LOGO_PATH))
    return _logo_reader


def draw_watermark(c, width, height, *, alpha: float = 0.06, scale: float = 0.6) -> None:
    """Logo GATHE en filigrane : centré, à ``scale`` de la largeur, opacité ``alpha``.

    ``c`` = canvas reportlab, ``width``/``height`` = dimensions de la page.
    À appeler AVANT de dessiner le contenu (le filigrane reste en arrière-plan).
    """
    try:
        img = _logo()
        iw, ih = img.getSize()
        if not iw or not ih:
            return
        target_w = width * scale
        target_h = target_w * ih / iw
        x = (width - target_w) / 2
        y = (height - target_h) / 2
        c.saveState()
        try:
            # Opacité constante appliquée aussi aux images (ExtGState /ca).
            c.setFillAlpha(alpha)
            c.setStrokeAlpha(alpha)
        except Exception:  # noqa: BLE001 — vieux reportlab sans alpha → filigrane opaque évité
            c.restoreState()
            return
        c.drawImage(
            img, x, y, width=target_w, height=target_h,
            mask="auto", preserveAspectRatio=True,
        )
        c.restoreState()
    except Exception:  # noqa: BLE001 — le filigrane ne doit jamais casser le PDF
        logger.warning("Filigrane GATHE non dessiné (best-effort).", exc_info=True)
