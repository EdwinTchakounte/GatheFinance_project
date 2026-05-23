"""Génération de l'attestation d'adhésion (PDF) — pièce jointe de l'e-mail
de bienvenue (UC1).

Pur : ne fait pas d'I/O réseau, ne touche pas à la base. Prend un ``Member``
et rend les octets d'un PDF A4 d'une page, prêt à être joint via
``send_template(..., attachments=[("attestation_adhesion.pdf", pdf, "application/pdf")])``.

Auto-contenu (pas de dépendance à un logo externe : le conteneur backend ne
contient pas les assets du frontend) — l'en-tête est dessiné en texte + filets
aux couleurs de la marque.
"""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# Couleurs de marque (logo : bleu + vert), alignées sur les tokens front.
BRAND_BLUE = colors.HexColor("#0E4D92")
BRAND_GREEN = colors.HexColor("#1B9E5A")
INK = colors.HexColor("#1A2230")
MUTED = colors.HexColor("#5B6472")

_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _fr_date(d: date) -> str:
    """1er janvier 2026 / 14 mai 2026 — format lisible FR."""
    jour = "1ᵉʳ" if d.day == 1 else str(d.day)
    return f"{jour} {_MOIS_FR[d.month - 1]} {d.year}"


def build_attestation_pdf(member) -> bytes:
    """Rend l'attestation d'adhésion de ``member`` en octets PDF (A4, 1 page)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 22 * mm

    c.setTitle(f"Attestation d'adhésion — {member.numero_membre}")
    c.setAuthor("Gathé Finance")

    # --- En-tête de marque -------------------------------------------------
    top = height - margin
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, top, "GATHÉ FINANCE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10.5)
    c.drawString(margin, top - 16, "Coopérative d'Épargne et de Crédit")

    # Double filet bleu + vert sous l'en-tête.
    rule_y = top - 28
    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(2)
    c.line(margin, rule_y, width - margin, rule_y)
    c.setStrokeColor(BRAND_GREEN)
    c.setLineWidth(1)
    c.line(margin, rule_y - 3, width - margin, rule_y - 3)

    # --- Titre -------------------------------------------------------------
    title_y = rule_y - 38
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, title_y, "ATTESTATION D'ADHÉSION")

    # --- Corps -------------------------------------------------------------
    nom_complet = f"{member.prenom} {member.nom}".strip()
    adhesion = _fr_date(member.date_adhesion or date.today())

    lines = [
        ("La direction de la coopérative Gathé Finance atteste que :", False),
        ("", False),
        (nom_complet, "name"),
        ("", False),
        (
            "a été admis(e) en qualité de membre de la coopérative, "
            "à l'issue de l'entretien d'admission prévu par le Règlement Intérieur.",
            False,
        ),
        ("", False),
    ]

    c.setFont("Helvetica", 11.5)
    text_y = title_y - 34
    line_h = 16
    for content, kind in lines:
        if kind == "name":
            c.setFillColor(BRAND_BLUE)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(width / 2, text_y, content)
            c.setFont("Helvetica", 11.5)
            c.setFillColor(INK)
        else:
            c.setFillColor(INK)
            for wrapped in _wrap(content, c, "Helvetica", 11.5, width - 2 * margin):
                c.drawString(margin, text_y, wrapped)
                text_y -= line_h
            continue
        text_y -= line_h

    # --- Encadré récapitulatif --------------------------------------------
    box_top = text_y - 4
    box_h = 30 * mm
    box_y = box_top - box_h
    c.setFillColor(colors.HexColor("#F4F7FB"))
    c.setStrokeColor(colors.HexColor("#D7E0EC"))
    c.setLineWidth(1)
    c.roundRect(margin, box_y, width - 2 * margin, box_h, 6, stroke=1, fill=1)

    rows = [
        ("Numéro de membre", member.numero_membre),
        ("Date d'adhésion", adhesion),
        ("Téléphone", member.phone or "—"),
    ]
    row_y = box_top - 12
    for label, value in rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(margin + 10, row_y, label.upper())
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(width - margin - 10, row_y, str(value))
        row_y -= 9 * mm

    # --- Mention activation ------------------------------------------------
    note_y = box_y - 18
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 9.5)
    for wrapped in _wrap(
        "Le statut de membre devient pleinement actif après règlement de la "
        "première cotisation (frais d'adhésion et d'inscription).",
        c, "Helvetica-Oblique", 9.5, width - 2 * margin,
    ):
        c.drawString(margin, note_y, wrapped)
        note_y -= 13

    # --- Pied de page : lieu, date d'émission, signature -------------------
    foot_y = margin + 26 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica", 10.5)
    c.drawString(margin, foot_y, f"Fait à Douala, le {_fr_date(date.today())}.")

    c.setFont("Helvetica-Bold", 10.5)
    c.drawRightString(width - margin, foot_y, "Pour la coopérative,")
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(MUTED)
    c.drawRightString(width - margin, foot_y - 14, "La Direction")

    # Filet de pied + mention légère.
    c.setStrokeColor(colors.HexColor("#D7E0EC"))
    c.setLineWidth(0.7)
    c.line(margin, margin + 10 * mm, width - margin, margin + 10 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        width / 2, margin + 6 * mm,
        "Gathé Finance — Akwa, Douala · Document généré automatiquement.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()


def _wrap(text: str, c, font: str, size: float, max_width: float) -> list[str]:
    """Retour à la ligne mot-à-mot selon la largeur de chaîne réelle."""
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
