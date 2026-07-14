"""Reçu de versement (mini-facture PDF) d'un ``Payment``.

Une fiche A4 d'une page qui atteste un versement du membre, avec les variables
importantes selon le type d'action (montant, frais de transaction, taux
d'intérêt applicable, dates, référence, statut). Miroir serveur du reçu généré
côté mobile — sert au **portail web** et à toute pièce justificative.

Même charte que ``loans/note_pdf.py`` / ``members/attestation.py`` (couleurs
marque, filets bicolores, filigrane logo). Aucune I/O réseau ; aucun accès DB
hors des objets passés en argument (le taux est résolu via ``rates.get_rate``,
qui a un fallback réglementaire sûr).
"""
from __future__ import annotations

import io
from datetime import date, datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps_coop.pdf_watermark import draw_watermark

from .models import Payment, RateParam
from .rates import get_rate


BRAND_BLUE = colors.HexColor("#0E4D92")
BRAND_GREEN = colors.HexColor("#1B9E5A")
INK = colors.HexColor("#1A2230")
MUTED = colors.HexColor("#5B6472")
PANEL_BORDER = colors.HexColor("#D7E0EC")

_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

_STATUT_LABEL = {
    "valide": "Validé",
    "en_attente": "En attente",
    "rejete": "Rejeté",
    "annule": "Annulé",
}


def _fr_datetime(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, datetime):
        jour = "1ᵉʳ" if d.day == 1 else str(d.day)
        return f"{jour} {_MOIS_FR[d.month - 1]} {d.year} à {d:%H:%M}"
    if isinstance(d, date):
        jour = "1ᵉʳ" if d.day == 1 else str(d.day)
        return f"{jour} {_MOIS_FR[d.month - 1]} {d.year}"
    return str(d)


def _fmt_xaf(montant) -> str:
    if montant is None:
        return "—"
    return f"{int(Decimal(montant)):,} XAF".replace(",", " ")


def _rate_line_for(payment: Payment) -> tuple[str, str] | None:
    """Ligne « taux » pertinente selon le type de versement (ratio → %)."""
    code = None
    label = None
    if payment.type == Payment.Type.REMBOURSEMENT:
        code, label = RateParam.Code.LOAN_INTEREST, "Taux d'intérêt du crédit"
    elif payment.type in (Payment.Type.EPARGNE_CLASSIQUE, Payment.Type.EPARGNE):
        code = RateParam.Code.SAVINGS_INTEREST_MONTHLY
        label = "Taux d'intérêt épargne (mensuel)"
    if code is None:
        return None
    try:
        taux = get_rate(code)
    except Exception:  # noqa: BLE001 — jamais bloquant
        return None
    if taux is None or Decimal(taux) <= 0:
        return None
    return label, f"{float(taux) * 100:.2f} %"


def build_payment_receipt(payment: Payment) -> bytes:
    """Rend le reçu de versement PDF (A4, 1 page) en bytes."""
    member = payment.member

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    draw_watermark(c, width, height)
    margin = 20 * mm

    receipt_ref = f"Reçu N° {payment.id:06d}"
    c.setTitle(f"Reçu de versement — {member.numero_membre} — #{payment.id}")
    c.setAuthor("GATHE Finance")

    # --- En-tête de marque -------------------------------------------------
    top = height - margin
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, top, "GATHE FINANCE")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10.5)
    c.drawString(margin, top - 16, "Coopérative d'Épargne et de Crédit")

    rule_y = top - 28
    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(2)
    c.line(margin, rule_y, width - margin, rule_y)
    c.setStrokeColor(BRAND_GREEN)
    c.setLineWidth(1)
    c.line(margin, rule_y - 3, width - margin, rule_y - 3)

    title_y = rule_y - 24
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, title_y, "REÇU DE VERSEMENT")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(
        width / 2,
        title_y - 13,
        f"{receipt_ref} · Émis le {_fr_datetime(date.today())}",
    )

    # --- Helpers de section/ligne -----------------------------------------
    def _section_header(label: str, anchor_y: float) -> float:
        c.setFillColor(BRAND_BLUE)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(margin, anchor_y, label.upper())
        c.setStrokeColor(PANEL_BORDER)
        c.setLineWidth(0.5)
        c.line(margin, anchor_y - 3, width - margin, anchor_y - 3)
        return anchor_y - 14

    def _row(label: str, value: str, anchor_y: float, *, bold_value: bool = False) -> float:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(margin, anchor_y, label)
        c.setFillColor(INK)
        c.setFont(
            "Helvetica-Bold" if bold_value else "Helvetica",
            11 if bold_value else 10.5,
        )
        c.drawRightString(width - margin, anchor_y, value or "—")
        return anchor_y - 14

    # --- Bloc Membre -------------------------------------------------------
    y = title_y - 32
    y = _section_header("Membre", y)
    y = _row("Nom complet", f"{member.prenom} {member.nom}".strip(), y, bold_value=True)
    y = _row("Numéro de membre", member.numero_membre, y)

    # --- Panneau MONTANT mis en valeur (info clé du reçu) -----------------
    statut_label = _STATUT_LABEL.get(payment.statut, payment.statut)
    y -= 12
    panel_h = 58
    panel_bottom = y - panel_h
    c.setFillColor(colors.HexColor("#EFF4FA"))
    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(0.8)
    c.roundRect(margin, panel_bottom, width - 2 * margin, panel_h, 8, stroke=1, fill=1)
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(margin + 14, y - 18, payment.get_type_display().upper())
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 23)
    c.drawString(margin + 14, y - 43, _fmt_xaf(payment.montant))
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawRightString(width - margin - 14, y - 18, f"Statut : {statut_label}")
    y = panel_bottom - 20

    # --- Bloc Opération ----------------------------------------------------
    y = _section_header("Opération", y)
    y = _row("Type de versement", payment.get_type_display(), y, bold_value=True)
    y = _row("Montant versé", _fmt_xaf(payment.montant), y, bold_value=True)
    if payment.frais_transaction and payment.frais_transaction > 0:
        y = _row("Frais de transaction", _fmt_xaf(payment.frais_transaction), y)
        total = Decimal(payment.montant) + Decimal(payment.frais_transaction)
        y = _row("Total débité", _fmt_xaf(total), y, bold_value=True)

    rate = _rate_line_for(payment)
    if rate is not None:
        y = _row(rate[0], rate[1], y)

    if payment.type == Payment.Type.EPARGNE and payment.nb_jours_couverts > 1:
        y = _row("Jours de collecte couverts", str(payment.nb_jours_couverts), y)
    if payment.type == Payment.Type.EPARGNE_CLASSIQUE:
        y = _row("Sous-canal", "Placement" if payment.is_placement else "Libre", y)

    # (Statut affiché dans le panneau montant ci-dessus.)

    # --- Bloc Traçabilité --------------------------------------------------
    y -= 4
    y = _section_header("Traçabilité", y)
    y = _row("Date du versement", _fr_datetime(payment.date_versement), y)
    if payment.date_validation:
        y = _row("Date de validation", _fr_datetime(payment.date_validation), y)
    if payment.reference_externe:
        y = _row("Référence", payment.reference_externe, y)

    # --- Footer ------------------------------------------------------------
    c.setStrokeColor(PANEL_BORDER)
    c.setLineWidth(0.7)
    c.line(margin, margin + 10 * mm, width - margin, margin + 10 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        width / 2, margin + 6 * mm,
        "GATHE Finance — Akwa, Douala · Reçu généré automatiquement, à conserver.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
