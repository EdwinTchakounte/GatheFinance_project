"""CH-9 — Génération de la « Note de demande de crédit » (PDF).

Une fiche A4 d'une page, signable, qui récapitule la demande du membre :
identité, montant, durée, motif, modalité de remboursement, moyen de
réception choisi, et — si la demande a été approuvée et un Loan créé —
l'échéancier prévisionnel.

Le PDF est attaché à l'e-mail Tara (pour les payouts Mobile Money) et
téléchargeable par le membre et l'admin via l'endpoint ``loan_request_note``.

Pas d'I/O réseau, pas d'accès DB hors objets passés en argument. Le style
suit ``apps_coop/members/attestation.py`` (mêmes couleurs marque, mêmes
filets, même utilitaire ``_wrap``).
"""
from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps_coop.pdf_letterhead import BRAND_BLUE, draw_header, draw_footer
from apps_coop.pdf_watermark import draw_watermark


INK = colors.HexColor("#1A2230")
MUTED = colors.HexColor("#5B6472")
PANEL_BG = colors.HexColor("#F4F7FB")
PANEL_BORDER = colors.HexColor("#D7E0EC")

_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]

_MOYEN_RECEPTION_LABEL = {
    "tara_om": "Orange Money (Tara)",
    "tara_momo": "MTN Mobile Money (Tara)",
    "agence_especes": "Retrait espèces en agence",
}

_MODALITE_LABEL = {
    "journalier": "Journalière",
    "hebdomadaire": "Hebdomadaire",
    "mensuel": "Mensuelle",
}


def _fr_date(d: date | None) -> str:
    if d is None:
        return "—"
    jour = "1ᵉʳ" if d.day == 1 else str(d.day)
    return f"{jour} {_MOIS_FR[d.month - 1]} {d.year}"


def _fmt_xaf(montant: Decimal | int | float | None) -> str:
    if montant is None:
        return "—"
    return f"{int(Decimal(montant)):,} XAF".replace(",", " ")


def _mask_phone(phone: str) -> str:
    p = (phone or "").strip()
    if len(p) < 6:
        return p
    return p[:4] + "•••" + p[-2:]


def _wrap(text: str, c, font: str, size: float, max_width: float) -> list[str]:
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


def build_loan_request_note(loan_request) -> bytes:
    """Rend la note de demande PDF (A4, 1 page) en bytes.

    Accepte une ``LoanRequest`` à n'importe quel statut : si un ``Loan`` est
    déjà créé (``loan_request.loan``), l'échéancier prévisionnel est ajouté.
    """
    loan = getattr(loan_request, "loan", None)
    member = loan_request.member

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    # Filigrane logo GATHE en arrière-plan (avant tout contenu).
    draw_watermark(c, width, height)
    margin = 20 * mm

    c.setTitle(
        f"Note de demande crédit — {member.numero_membre} — #{loan_request.id}"
    )
    c.setAuthor("GATHE Finance")

    # --- En-tête + pied officiels (papier à en-tête) -----------------------
    content_top = draw_header(c, width, height, margin=margin)
    draw_footer(c, width, margin=margin)

    # Titre + référence demande.
    title_y = content_top - 8
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, title_y, "NOTE DE DEMANDE DE CRÉDIT")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    ref = (
        loan.numero_dossier if loan and loan.numero_dossier
        else f"Demande #{loan_request.id}"
    )
    c.drawCentredString(
        width / 2,
        title_y - 13,
        f"Référence : {ref} · Émis le {_fr_date(date.today())}",
    )

    # --- Bloc Demandeur ----------------------------------------------------
    y = title_y - 32

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

    y = _section_header("Demandeur", y)
    y = _row("Nom complet", member.nom_complet, y, bold_value=True)
    y = _row("Numéro de membre", member.numero_membre, y)
    y = _row("Téléphone", member.phone or "—", y)

    # --- Bloc Demande ------------------------------------------------------
    y -= 4
    y = _section_header("Demande", y)
    y = _row(
        "Montant demandé",
        _fmt_xaf(loan_request.montant_demande),
        y,
        bold_value=True,
    )
    y = _row("Durée", f"{loan_request.duree_mois} mois", y)
    modalite = _MODALITE_LABEL.get(
        loan_request.modalite_paiement, loan_request.modalite_paiement or "—"
    )
    y = _row("Modalité de remboursement", modalite, y)

    # Motif sur plusieurs lignes (wrap).
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, "Motif")
    y -= 12
    c.setFillColor(INK)
    c.setFont("Helvetica", 10.5)
    motif_wrapped = _wrap(
        loan_request.motif or "—", c, "Helvetica", 10.5, width - 2 * margin
    )
    for line in motif_wrapped[:4]:
        c.drawString(margin, y, line)
        y -= 12
    if len(motif_wrapped) > 4:
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(margin, y, "… (motif tronqué pour tenir sur une page)")
        y -= 12

    # --- Bloc Moyen de réception ------------------------------------------
    y -= 2
    y = _section_header("Moyen de réception choisi", y)
    canal_label = _MOYEN_RECEPTION_LABEL.get(
        loan_request.moyen_reception, "Non précisé"
    )
    y = _row("Canal", canal_label, y, bold_value=True)
    if loan_request.moyen_reception in ("tara_om", "tara_momo"):
        y = _row("Numéro Mobile Money", _mask_phone(loan_request.recipient_phone), y)
    else:
        y = _row("Numéro Mobile Money", "Sans objet (retrait espèces)", y)

    # --- Bloc Échéancier prévisionnel (si Loan créé) ----------------------
    if loan is not None:
        y -= 2
        y = _section_header("Échéancier prévisionnel", y)

        # CH-11 — Si retenue à la source, on affiche le NET d'abord (c'est
        # ce que le membre va réellement toucher) et la retenue d'intérêts.
        mode_source = (
            getattr(loan, "mode_retenue_interets", "echeances") == "source"
        )
        if mode_source and loan.montant_decaisse_net is not None:
            y = _row(
                "Net versé au membre",
                _fmt_xaf(loan.montant_decaisse_net),
                y,
                bold_value=True,
            )
            y = _row(
                "Intérêts retenus à la source",
                f"− {_fmt_xaf(loan.interets_retenus_source)}",
                y,
            )
        y = _row(
            "Montant total dû",
            _fmt_xaf(loan.montant_total_du),
            y,
            bold_value=True,
        )
        y = _row(
            "Taux d'intérêt (flat)",
            f"{float(loan.taux_interet) * 100:.2f} %",
            y,
        )
        y = _row(
            "Date 1ère échéance",
            _fr_date(loan.date_premiere_echeance),
            y,
        )
        if loan.date_butoire:
            y = _row("Date butoire", _fr_date(loan.date_butoire), y)

        # Mini-tableau des 4 premières échéances (s'il y en a).
        installments = list(loan.installments.order_by("numero_echeance")[:4])
        if installments:
            c.setFillColor(MUTED)
            c.setFont("Helvetica-Bold", 9)
            # Colonnes élargies : la date est un libellé FR complet ("15
            # septembre 2026", ~90pt) — avec l'ancien margin+70 pour « Capital »
            # elle chevauchait le montant. Écart suffisant N°→date→capital→total.
            col_x = [margin, margin + 24, margin + 132, margin + 210, width - margin]
            headers = ["N°", "Échéance", "Capital", "Total dû"]
            for i, h in enumerate(headers):
                if i == 0:
                    c.drawString(col_x[i], y, h)
                elif i == len(headers) - 1:
                    c.drawRightString(col_x[-1], y, h)
                else:
                    c.drawString(col_x[i], y, h)
            y -= 11
            c.setStrokeColor(PANEL_BORDER)
            c.setLineWidth(0.4)
            c.line(margin, y + 6, width - margin, y + 6)
            c.setFillColor(INK)
            c.setFont("Helvetica", 9.5)
            for inst in installments:
                c.drawString(col_x[0], y, str(inst.numero_echeance))
                c.drawString(col_x[1], y, _fr_date(inst.date_echeance))
                c.drawString(col_x[2], y, _fmt_xaf(inst.montant_capital))
                c.drawRightString(col_x[-1], y, _fmt_xaf(inst.montant_total))
                y -= 12
            total_count = loan.installments.count()
            if total_count > 4:
                c.setFillColor(MUTED)
                c.setFont("Helvetica-Oblique", 9)
                c.drawString(
                    margin, y,
                    f"… {total_count - 4} échéance(s) supplémentaire(s) — "
                    "détail dans le portail.",
                )
                y -= 12

    # --- Bloc Signatures + footer ----------------------------------------
    # On colle les signatures en bas pour garantir l'aspect signable.
    sig_y = margin + 30 * mm
    c.setStrokeColor(PANEL_BORDER)
    c.setLineWidth(0.5)
    c.line(margin, sig_y + 18, margin + 60 * mm, sig_y + 18)
    c.line(width - margin - 60 * mm, sig_y + 18, width - margin, sig_y + 18)

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, sig_y, "Signature du membre")
    c.drawRightString(width - margin, sig_y, "Pour la coopérative")
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(margin, sig_y - 12, member.nom_complet)
    c.drawRightString(width - margin, sig_y - 12, "La Direction")

    c.showPage()
    c.save()
    return buf.getvalue()
