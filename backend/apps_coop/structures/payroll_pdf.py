"""PDF « État de paie du mois » d'une structure (registre d'un lot de paie).

Une fiche A4 : en-tête coopérative, structure + période, tableau des employés
(nom, poste, salaire versé, date), et le total de la masse salariale versée.
"""
from __future__ import annotations

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps_coop.pdf_letterhead import BRAND_BLUE, draw_footer, draw_header
from apps_coop.pdf_watermark import draw_watermark

from .models import PayrollRun


def _fmt_xaf(v) -> str:
    return f"{int(Decimal(v)):,} FCFA".replace(",", " ")


def build_payroll_pdf(run: PayrollRun) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm

    draw_watermark(c, width, height)
    y = draw_header(c, width, height, margin=margin)
    draw_footer(c, width, margin=margin)

    # Titre
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, y - 6 * mm, "État de paie du mois")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)
    c.drawString(margin, y - 13 * mm, f"Structure : {run.structure.nom}")
    c.drawString(margin, y - 19 * mm, f"Période : {run.periode}")
    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(
        margin, y - 24 * mm,
        f"Édité le {run.created_at.strftime('%d/%m/%Y')} · "
        f"{run.employes_count} employé(s)",
    )

    # En-tête tableau
    top = y - 33 * mm
    c.setFillColor(BRAND_BLUE)
    c.rect(margin, top - 6 * mm, width - 2 * margin, 6 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 3 * mm, top - 4.3 * mm, "Employé")
    c.drawString(margin + 70 * mm, top - 4.3 * mm, "Poste")
    c.drawRightString(width - margin - 3 * mm, top - 4.3 * mm, "Salaire versé")

    # Lignes
    rows = (
        run.transactions.select_related("member")
        .filter(type_op="versement_paie")
        .order_by("member__nom", "member__prenom")
    )
    ly = top - 6 * mm
    c.setFont("Helvetica", 9)
    total = Decimal("0")
    for i, t in enumerate(rows):
        ly -= 7 * mm
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F3F6FB"))
            c.rect(margin, ly - 1.5 * mm, width - 2 * margin, 7 * mm, stroke=0, fill=1)
        c.setFillColor(colors.black)
        nom = (
            f"{t.member.prenom} {t.member.nom}".strip()
            if t.member else "(retiré)"
        )
        numero = t.member.numero_membre if t.member else ""
        emp = next(
            (
                e for e in run.structure.employees.all()
                if t.member_id and e.member_id == t.member_id
            ),
            None,
        )
        poste = emp.poste if emp else ""
        c.drawString(margin + 3 * mm, ly + 1.5 * mm, f"{nom}")
        c.setFillColor(colors.HexColor("#888888"))
        c.setFont("Helvetica", 7)
        c.drawString(margin + 3 * mm, ly - 1 * mm, numero)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        c.drawString(margin + 70 * mm, ly + 1.5 * mm, poste[:28])
        c.drawRightString(width - margin - 3 * mm, ly + 1.5 * mm, _fmt_xaf(t.montant))
        total += Decimal(t.montant)

    # Total
    ly -= 10 * mm
    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(1)
    c.line(margin + 90 * mm, ly + 5 * mm, width - margin, ly + 5 * mm)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(BRAND_BLUE)
    c.drawString(margin + 90 * mm, ly, "Masse salariale versée")
    c.drawRightString(width - margin - 3 * mm, ly, _fmt_xaf(total))

    c.showPage()
    c.save()
    return buf.getvalue()
