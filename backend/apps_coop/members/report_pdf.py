"""Rapports PDF — photo de la coopérative + relevé par membre.

Deux livrables staff (reportlab, A4, style marque aligné sur ``attestation.py``
et ``loans/note_pdf.py``) :

  * ``build_coop_report()`` — état instantané de la coopérative : KPI, graphiques
    (répartition épargne, portefeuille crédit, membres par statut) et surtout un
    bloc « Actions à mener » (files d'attente + alertes), pour une lecture rapide
    et actionnable.
  * ``build_member_statement(member)`` — relevé d'un membre : épargne (collecte +
    classique + placement), crédits, carnets, dernières écritures.

La collecte de données est une **photo instantanée** (pas de cumuls historiques
coûteux). Elle vit dans ``collect_coop_report_data`` / ``collect_member_data``,
séparée du rendu — testable sans générer de PDF.
"""
from __future__ import annotations

import io
from datetime import date, timedelta
from decimal import Decimal

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps_coop.pdf_letterhead import draw_header, draw_footer
from apps_coop.pdf_watermark import draw_watermark


# Couleurs de marque réelles (logo GATHE) ; vert foncé pour rester lisible
# sur fond blanc dans le corps (montants, graphiques, légendes).
BRAND_BLUE = colors.HexColor("#0747FF")
BRAND_GREEN = colors.HexColor("#14820E")
INK = colors.HexColor("#1A2230")
MUTED = colors.HexColor("#5B6472")
PANEL_BG = colors.HexColor("#F4F7FB")
PANEL_BORDER = colors.HexColor("#D7E0EC")
WARN = colors.HexColor("#B9761A")
BAD = colors.HexColor("#CC3B56")

# Palette des graphiques (cohérente avec les tokens web).
CHART_COLORS = [
    colors.HexColor("#0E4D92"),  # bleu
    colors.HexColor("#1B9E5A"),  # vert
    colors.HexColor("#D98A1A"),  # ambre
    colors.HexColor("#CC3B56"),  # rose
    colors.HexColor("#6C7A91"),  # gris
]

_MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


# Types d'écriture épargne classique qui CRÉDITENT le solde (sens « + »). Tout
# le reste (retraits, frais, saisies) débite. Comparé par valeur string pour
# éviter d'importer le modèle au niveau module.
_CLASSIC_CREDIT_TYPE_VALUES = frozenset({
    "depot",
    "interet",
    "interet_preteur",
    "interet_placement",
    "restitution_maturite",
    "bascule_collecte",
})


def _classic_sens(type_op_value: str) -> str:
    return "+" if type_op_value in _CLASSIC_CREDIT_TYPE_VALUES else "−"


def _fr_date(d: date | None) -> str:
    if d is None:
        return "—"
    return f"{d.day} {_MOIS_FR[d.month]} {d.year}"


def _fmt_xaf(montant) -> str:
    try:
        n = int(round(float(montant)))
    except (TypeError, ValueError):
        return "0"
    return f"{n:,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Collecte de données — photo instantanée
# ---------------------------------------------------------------------------


def collect_coop_report_data() -> dict:
    """Agrège l'état courant de la coopérative. Aucun cumul historique."""
    from django.db.models import Sum

    from apps_coop.loans.models import (
        AvalisteConsent,
        JudicialEscalation,
        Loan,
        LoanRequest,
    )
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        LenderConsent,
        LenderTranche,
        SavingsAccount,
    )

    from .models import Member, MembershipRequest

    def _sum(qs, field="montant"):
        return qs.aggregate(s=Sum(field))["s"] or Decimal("0")

    today = date.today()

    # Membres.
    members = {
        "actif": Member.objects.filter(statut=Member.Statut.ACTIF).count(),
        "suspendu": Member.objects.filter(statut=Member.Statut.SUSPENDU).count(),
        "temporaire": Member.objects.filter(statut=Member.Statut.TEMPORAIRE).count(),
        "radie": Member.objects.filter(statut=Member.Statut.RADIE).count(),
    }
    members["total"] = sum(members.values())
    # Réinscriptions en retard (échéance dépassée) — action à mener.
    reinscription_overdue = Member.objects.filter(
        statut=Member.Statut.ACTIF,
        date_derniere_reinscription__lte=today - timedelta(days=365),
    ).count()

    # Épargne — solde classique INCLUT déjà le placement (ne pas additionner).
    collecte = _sum(SavingsAccount.objects.all(), "solde")
    classique = _sum(ClassicSavingsAccount.objects.all(), "solde")
    placement = _sum(
        LenderTranche.objects.filter(statut__in=LenderTranche.STATUTS_ACTIFS),
        "montant",
    )
    classique_libre = Decimal(classique) - Decimal(placement)
    if classique_libre < 0:
        classique_libre = Decimal("0")
    epargne = {
        "collecte": Decimal(collecte),
        "classique": Decimal(classique),
        "classique_libre": classique_libre,
        "placement": Decimal(placement),
        "total": Decimal(collecte) + Decimal(classique),
    }

    # Crédit.
    actifs_qs = Loan.objects.filter(statut=Loan.Statut.ACTIF)
    retard_qs = Loan.objects.filter(statut=Loan.Statut.EN_RETARD)
    contentieux_qs = Loan.objects.filter(statut=Loan.Statut.CONTENTIEUX)
    credit = {
        "encours": _sum(actifs_qs | retard_qs, "solde_restant"),
        "n_actifs": actifs_qs.count(),
        "n_retard": retard_qs.count(),
        "montant_retard": _sum(retard_qs, "solde_restant"),
        "n_contentieux": contentieux_qs.count(),
        "montant_contentieux": _sum(contentieux_qs, "solde_restant"),
    }

    # Pool prêteur.
    lenders = {
        "consents_actifs": LenderConsent.objects.filter(revoked_at__isnull=True).count(),
        "disponible": _sum(
            LenderTranche.objects.filter(statut=LenderTranche.Statut.DISPONIBLE)
        ),
        "gelee": _sum(
            LenderTranche.objects.filter(statut=LenderTranche.Statut.GELEE)
        ),
        "engagee": _sum(
            LenderTranche.objects.filter(statut=LenderTranche.Statut.ENGAGEE)
        ),
    }

    # Files d'attente = actions immédiates.
    queues = {
        "adhesions": MembershipRequest.objects.filter(
            statut=MembershipRequest.Statut.EN_ATTENTE
        ).count(),
        "credits_instruction": LoanRequest.objects.filter(
            statut=LoanRequest.Statut.EN_INSTRUCTION
        ).count(),
        "avaliste_pending": AvalisteConsent.objects.filter(
            statut=AvalisteConsent.Statut.PENDING
        ).count(),
        "campaign_validation": LoanRequest.objects.filter(
            statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE
        ).count(),
    }

    # Alertes = risques à surveiller.
    alerts = {
        "reinscription_overdue": reinscription_overdue,
        "loans_en_retard": credit["n_retard"],
        "loans_contentieux": credit["n_contentieux"],
        "escalades_ouvertes": JudicialEscalation.objects.filter(
            statut__in=[
                JudicialEscalation.Statut.EN_INSTANCE,
                JudicialEscalation.Statut.DECISION_RENDUE,
            ]
        ).count(),
    }

    return {
        "generated_at": today,
        "members": members,
        "epargne": epargne,
        "credit": credit,
        "lenders": lenders,
        "queues": queues,
        "alerts": alerts,
    }


def collect_member_data(member) -> dict:
    """Photo de la situation d'un membre (épargne, crédits, carnets, écritures)."""
    from django.db.models import Sum

    from apps_coop.loans.models import Loan
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )

    from .models import BookletOrder

    collecte_acc = SavingsAccount.objects.filter(member=member).first()
    classic_acc = ClassicSavingsAccount.objects.filter(member=member).first()

    collecte_solde = Decimal(collecte_acc.solde) if collecte_acc else Decimal("0")
    classique_solde = Decimal(classic_acc.solde) if classic_acc else Decimal("0")
    placement = (
        Decimal(classic_acc.solde_placement_actif) if classic_acc else Decimal("0")
    )
    classique_libre = classique_solde - placement
    if classique_libre < 0:
        classique_libre = Decimal("0")

    # Dernières écritures (collecte + classique fusionnées, 12 plus récentes).
    ecritures = []
    for t in SavingsTransaction.objects.filter(account__member=member).order_by(
        "-date", "-id"
    )[:12]:
        ecritures.append({
            "date": t.date.date() if hasattr(t.date, "date") else t.date,
            "produit": "Collecte",
            "type": t.get_type_op_display(),
            "montant": Decimal(t.montant),
            "sens": "+" if t.type_op == SavingsTransaction.TypeOp.DEPOT else "−",
        })
    for t in ClassicSavingsTransaction.objects.filter(
        account__member=member
    ).order_by("-date", "-id")[:12]:
        ecritures.append({
            "date": t.date.date() if hasattr(t.date, "date") else t.date,
            "produit": "Classique",
            "type": t.get_type_op_display(),
            "montant": Decimal(t.montant),
            "sens": _classic_sens(t.type_op),
        })
    ecritures.sort(key=lambda e: e["date"], reverse=True)
    ecritures = ecritures[:14]

    loans = []
    for loan in Loan.objects.filter(member=member).order_by("-date_decaissement")[:8]:
        loans.append({
            "numero": loan.numero_dossier,
            "montant": Decimal(loan.montant),
            "solde_restant": Decimal(loan.solde_restant),
            "statut": loan.get_statut_display(),
        })

    booklets = list(
        BookletOrder.objects.filter(member=member).order_by("-created_at")[:6]
    )

    return {
        "generated_at": date.today(),
        "member": member,
        "epargne": {
            "collecte": collecte_solde,
            "classique": classique_solde,
            "classique_libre": classique_libre,
            "placement": placement,
            "total": collecte_solde + classique_solde,
        },
        "ecritures": ecritures,
        "loans": loans,
        "booklets": booklets,
    }


# ---------------------------------------------------------------------------
# Graphiques natifs reportlab
# ---------------------------------------------------------------------------


def _pie(values: list[float], labels: list[str], size: float = 46 * mm) -> Drawing:
    """Camembert. Les valeurs nulles/segments vides sont filtrés."""
    pairs = [(v, l) for v, l in zip(values, labels) if v and v > 0]
    d = Drawing(size, size)
    if not pairs:
        d.add(String(size / 2, size / 2, "aucune donnée", fontSize=8,
                      fillColor=MUTED, textAnchor="middle"))
        return d
    pie = Pie()
    pie.x = 4
    pie.y = 4
    pie.width = size - 8
    pie.height = size - 8
    pie.data = [p[0] for p in pairs]
    pie.labels = None
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    for i in range(len(pairs)):
        pie.slices[i].fillColor = CHART_COLORS[i % len(CHART_COLORS)]
    d.add(pie)
    return d


def _bars(values: list[float], labels: list[str], width: float, height: float,
          bar_colors: list | None = None) -> Drawing:
    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 22
    chart.y = 18
    chart.width = width - 34
    chart.height = height - 34
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7.5
    chart.categoryAxis.labels.fillColor = MUTED
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.labels.fillColor = MUTED
    chart.barWidth = 8
    chart.groupSpacing = 10
    palette = bar_colors or CHART_COLORS
    for i in range(len(values)):
        chart.bars[(0, i)].fillColor = palette[i % len(palette)]
    d.add(chart)
    return d


def _legend(c, x: float, y: float, items: list[tuple[str, colors.Color, str]]) -> float:
    """Légende compacte : (label, couleur, valeur). Retourne le y final."""
    for label, color, value in items:
        c.setFillColor(color)
        c.rect(x, y - 1.5, 7, 7, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 11, y, label)
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x + 11, y - 9, value)
        y -= 21
    return y


# ---------------------------------------------------------------------------
# En-tête de marque partagé
# ---------------------------------------------------------------------------


def _brand_header(c, width, height, margin, title: str, subtitle: str) -> float:
    draw_watermark(c, width, height)
    content_top = draw_header(c, width, height, margin=margin)
    title_y = content_top - 6
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, title_y, title)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(width / 2, title_y - 13, subtitle)
    return title_y - 30


def _kpi_card(c, x, y, w, h, label, value, sub=None, accent=BRAND_BLUE):
    c.setFillColor(PANEL_BG)
    c.setStrokeColor(PANEL_BORDER)
    c.setLineWidth(0.6)
    c.roundRect(x, y - h, w, h, 4, fill=1, stroke=1)
    c.setFillColor(accent)
    c.rect(x, y - h, 3, h, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(x + 9, y - 13, label.upper())
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(x + 9, y - 30, value)
    if sub:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(x + 9, y - 41, sub)


def _section_title(c, margin, width, y, label):
    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(margin, y, label.upper())
    c.setStrokeColor(PANEL_BORDER)
    c.setLineWidth(0.5)
    c.line(margin, y - 3, width - margin, y - 3)
    return y - 16


# ---------------------------------------------------------------------------
# Rapport global
# ---------------------------------------------------------------------------


def build_coop_report(data: dict | None = None) -> bytes:
    if data is None:
        data = collect_coop_report_data()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    c.setTitle("État de la coopérative — GATHE Finance")
    c.setAuthor("GATHE Finance")

    y = _brand_header(
        c, width, height, margin,
        "ÉTAT DE LA COOPÉRATIVE",
        f"Photo au {_fr_date(data['generated_at'])}",
    )

    ep = data["epargne"]
    cr = data["credit"]
    mb = data["members"]

    # --- Bandeau KPI (4 cartes) -------------------------------------------
    card_w = (width - 2 * margin - 3 * 6) / 4
    card_h = 46
    kpis = [
        ("Membres actifs", str(mb["actif"]), f"sur {mb['total']} inscrits", BRAND_BLUE),
        ("Épargne totale", _fmt_xaf(ep["total"]), "collecte + classique", BRAND_GREEN),
        ("Encours crédit", _fmt_xaf(cr["encours"]), f"{cr['n_actifs'] + cr['n_retard']} crédits", BRAND_BLUE),
        ("Pool prêteur libre", _fmt_xaf(data["lenders"]["disponible"]), "mobilisable", BRAND_GREEN),
    ]
    for i, (label, value, sub, accent) in enumerate(kpis):
        _kpi_card(c, margin + i * (card_w + 6), y, card_w, card_h, label, value, sub, accent)
    y -= card_h + 20

    # --- Graphiques (épargne pie + crédit bars) ---------------------------
    y = _section_title(c, margin, width, y, "Répartition & portefeuille")
    chart_top = y

    # Camembert épargne.
    pie = _pie(
        [float(ep["collecte"]), float(ep["classique_libre"]), float(ep["placement"])],
        ["Collecte", "Classique libre", "Placement"],
        size=44 * mm,
    )
    pie.drawOn(c, margin, chart_top - 44 * mm)
    _legend(
        c, margin + 48 * mm, chart_top - 6,
        [
            ("Collecte journalière", CHART_COLORS[0], _fmt_xaf(ep["collecte"]) + " XAF"),
            ("Classique libre", CHART_COLORS[1], _fmt_xaf(ep["classique_libre"]) + " XAF"),
            ("Placement", CHART_COLORS[2], _fmt_xaf(ep["placement"]) + " XAF"),
        ],
    )

    # Barres portefeuille crédit (encours par bucket).
    bars = _bars(
        [float(cr["encours"]), float(cr["montant_retard"]), float(cr["montant_contentieux"])],
        ["Sain", "En retard", "Contentieux"],
        width=76 * mm, height=44 * mm,
        bar_colors=[BRAND_GREEN, WARN, BAD],
    )
    bars.drawOn(c, width - margin - 76 * mm, chart_top - 44 * mm)
    y = chart_top - 44 * mm - 14

    # --- Actions à mener --------------------------------------------------
    y = _section_title(c, margin, width, y, "Actions à mener — files d'attente")
    q = data["queues"]
    action_items = [
        ("Adhésions à instruire", q["adhesions"]),
        ("Crédits en instruction", q["credits_instruction"]),
        ("Avalistes en attente de réponse", q["avaliste_pending"]),
        ("Candidatures campagne à valider", q["campaign_validation"]),
    ]
    y = _action_rows(c, margin, width, y, action_items, zero_is_ok=True)

    y -= 6
    y = _section_title(c, margin, width, y, "Alertes — à surveiller")
    a = data["alerts"]
    alert_items = [
        ("Réinscriptions annuelles en retard", a["reinscription_overdue"]),
        ("Crédits en retard de paiement", a["loans_en_retard"]),
        ("Crédits en contentieux", a["loans_contentieux"]),
        ("Escalades judiciaires ouvertes", a["escalades_ouvertes"]),
    ]
    y = _action_rows(c, margin, width, y, alert_items, zero_is_ok=True, danger=True)

    _footer(c, width, margin)
    c.showPage()
    c.save()
    return buf.getvalue()


def _action_rows(c, margin, width, y, items, *, zero_is_ok=False, danger=False):
    for label, count in items:
        is_zero = not count
        c.setFillColor(INK)
        c.setFont("Helvetica", 9.5)
        c.drawString(margin + 4, y, label)
        # Pastille compteur.
        if is_zero:
            badge_color = BRAND_GREEN if zero_is_ok else MUTED
            txt = "0"
        else:
            badge_color = BAD if danger else BRAND_BLUE
            txt = str(count)
        c.setFillColor(badge_color)
        bw = 20
        c.roundRect(width - margin - bw, y - 3, bw, 12, 6, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(width - margin - bw / 2, y, txt)
        y -= 16
    return y


def _footer(c, width, margin):
    draw_footer(c, width, margin=margin)


# ---------------------------------------------------------------------------
# Relevé par membre
# ---------------------------------------------------------------------------


def build_member_statement(member, data: dict | None = None) -> bytes:
    if data is None:
        data = collect_member_data(member)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    c.setTitle(f"Relevé — {member.numero_membre}")
    c.setAuthor("GATHE Finance")

    y = _brand_header(
        c, width, height, margin,
        "RELEVÉ DE SITUATION",
        f"{member.prenom} {member.nom} · {member.numero_membre} · émis le {_fr_date(data['generated_at'])}",
    )

    ep = data["epargne"]

    # --- KPI épargne (3 cartes) -------------------------------------------
    card_w = (width - 2 * margin - 2 * 6) / 3
    card_h = 46
    cards = [
        ("Épargne totale", _fmt_xaf(ep["total"]), "collecte + classique", BRAND_GREEN),
        ("Collecte journalière", _fmt_xaf(ep["collecte"]), "retirable fin de mois", BRAND_BLUE),
        ("Classique", _fmt_xaf(ep["classique"]), f"dont placement {_fmt_xaf(ep['placement'])}", BRAND_BLUE),
    ]
    for i, (label, value, sub, accent) in enumerate(cards):
        _kpi_card(c, margin + i * (card_w + 6), y, card_w, card_h, label, value, sub, accent)
    y -= card_h + 18

    # --- Crédits ----------------------------------------------------------
    y = _section_title(c, margin, width, y, "Crédits")
    if data["loans"]:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(margin + 4, y, "DOSSIER")
        c.drawString(margin + 70 * mm, y, "MONTANT")
        c.drawString(margin + 105 * mm, y, "SOLDE RESTANT")
        c.drawRightString(width - margin, y, "STATUT")
        y -= 13
        for lo in data["loans"]:
            c.setFillColor(INK)
            c.setFont("Helvetica", 9)
            c.drawString(margin + 4, y, lo["numero"] or "—")
            c.drawString(margin + 70 * mm, y, _fmt_xaf(lo["montant"]))
            c.drawString(margin + 105 * mm, y, _fmt_xaf(lo["solde_restant"]))
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8.5)
            c.drawRightString(width - margin, y, lo["statut"])
            y -= 13
    else:
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(margin + 4, y, "Aucun crédit.")
        y -= 13
    y -= 8

    # --- Dernières écritures ---------------------------------------------
    y = _section_title(c, margin, width, y, "Dernières écritures d'épargne")
    if data["ecritures"]:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(margin + 4, y, "DATE")
        c.drawString(margin + 32 * mm, y, "PRODUIT")
        c.drawString(margin + 60 * mm, y, "OPÉRATION")
        c.drawRightString(width - margin, y, "MONTANT")
        y -= 13
        for e in data["ecritures"]:
            if y < 30 * mm:
                break
            c.setFillColor(INK)
            c.setFont("Helvetica", 9)
            c.drawString(margin + 4, y, _fr_date(e["date"]))
            c.drawString(margin + 32 * mm, y, e["produit"])
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8.5)
            c.drawString(margin + 60 * mm, y, e["type"][:34])
            c.setFillColor(BRAND_GREEN if e["sens"] == "+" else BAD)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(width - margin, y, f"{e['sens']} {_fmt_xaf(e['montant'])}")
            y -= 13
    else:
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(margin + 4, y, "Aucune écriture.")
        y -= 13

    # --- Carnets (pied) ---------------------------------------------------
    if data["booklets"]:
        y -= 8
        y = _section_title(c, margin, width, y, "Carnets détenus")
        c.setFillColor(INK)
        c.setFont("Helvetica", 9)
        labels = [
            f"Carnet {b.annee or _fr_date(b.created_at.date() if hasattr(b.created_at,'date') else b.created_at)} ({b.get_statut_display()})"
            for b in data["booklets"]
        ]
        c.drawString(margin + 4, y, " · ".join(labels)[:110])

    _footer(c, width, margin)
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Relevé des écritures du carnet (membre) — paginé, TOUTES les écritures
# ---------------------------------------------------------------------------


def collect_member_ledger(member) -> dict:
    """TOUTES les écritures d'épargne du membre (collecte + classique).

    Fusionnées, triées par date décroissante, avec le carnet auquel chaque
    écriture est rattachée. Sert au relevé PDF téléchargeable par le membre.
    """
    from apps_coop.savings.models import (
        ClassicSavingsAccount,
        ClassicSavingsTransaction,
        SavingsAccount,
        SavingsTransaction,
    )

    def _booklet_label(row) -> str:
        b = getattr(row, "booklet_order", None)
        if b is None:
            return "—"
        return f"Carnet {b.annee}" if getattr(b, "annee", None) else "Carnet"

    entries = []
    for t in (
        SavingsTransaction.objects.filter(account__member=member)
        .select_related("booklet_order")
        .order_by("-date", "-id")
    ):
        entries.append({
            "date": t.date.date() if hasattr(t.date, "date") else t.date,
            "produit": "Collecte",
            "type": t.get_type_op_display(),
            "montant": Decimal(t.montant),
            "sens": "+" if t.type_op == SavingsTransaction.TypeOp.DEPOT else "−",
            "carnet": _booklet_label(t),
        })
    for t in (
        ClassicSavingsTransaction.objects.filter(account__member=member)
        .select_related("booklet_order")
        .order_by("-date", "-id")
    ):
        entries.append({
            "date": t.date.date() if hasattr(t.date, "date") else t.date,
            "produit": "Classique",
            "type": t.get_type_op_display(),
            "montant": Decimal(t.montant),
            "sens": _classic_sens(t.type_op),
            "carnet": _booklet_label(t),
        })
    entries.sort(key=lambda e: e["date"], reverse=True)

    collecte = SavingsAccount.objects.filter(member=member).first()
    classique = ClassicSavingsAccount.objects.filter(member=member).first()
    return {
        "generated_at": date.today(),
        "member": member,
        "entries": entries,
        "collecte_solde": Decimal(collecte.solde) if collecte else Decimal("0"),
        "classique_solde": Decimal(classique.solde) if classique else Decimal("0"),
    }


def _fit(c, text, font, size, max_w):
    """Tronque `text` à `max_w` (points), avec ellipse propre — jamais en
    plein milieu d'un mot coupé net. Mesure réelle via les métriques de police.
    """
    if c.stringWidth(text, font, size) <= max_w:
        return text
    ell = "…"
    while text and c.stringWidth(text + ell, font, size) > max_w:
        text = text[:-1]
    return text.rstrip() + ell


def _ledger_table_header(c, margin, width, y):
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(margin + 2, y, "DATE")
    c.drawString(margin + 26 * mm, y, "PRODUIT")
    c.drawString(margin + 54 * mm, y, "OPÉRATION")
    c.drawString(margin + 120 * mm, y, "CARNET")
    c.drawRightString(width - margin, y, "MONTANT")
    y -= 4
    c.setStrokeColor(PANEL_BORDER)
    c.setLineWidth(0.5)
    c.line(margin, y, width - margin, y)
    return y - 12


def build_member_ledger_pdf(member, data: dict | None = None) -> bytes:
    if data is None:
        data = collect_member_ledger(member)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    c.setTitle(f"Écritures du carnet — {member.numero_membre}")
    c.setAuthor("GATHE Finance")

    y = _brand_header(
        c, width, height, margin,
        "RELEVÉ DES ÉCRITURES",
        f"{member.prenom} {member.nom} · {member.numero_membre} · émis le "
        f"{_fr_date(data['generated_at'])}",
    )

    # Bandeau soldes.
    c.setFillColor(INK)
    c.setFont("Helvetica", 9.5)
    c.drawString(
        margin, y,
        f"Solde collecte : {_fmt_xaf(data['collecte_solde'])} XAF     "
        f"Solde classique : {_fmt_xaf(data['classique_solde'])} XAF     "
        f"{len(data['entries'])} écriture(s)",
    )
    y -= 18

    y = _ledger_table_header(c, margin, width, y)

    for e in data["entries"]:
        if y < 30 * mm:
            _footer(c, width, margin)
            c.showPage()
            y = _brand_header(
                c, width, height, margin,
                "RELEVÉ DES ÉCRITURES (SUITE)",
                f"{member.prenom} {member.nom} · {member.numero_membre}",
            )
            y = _ledger_table_header(c, margin, width, y)

        c.setFillColor(INK)
        c.setFont("Helvetica", 9)
        c.drawString(margin + 2, y, _fr_date(e["date"]))
        c.drawString(margin + 26 * mm, y, e["produit"])
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8.5)
        # Colonne OPÉRATION : largeur = de +54mm jusqu'à CARNET (+120mm),
        # moins un padding de 4mm pour ne jamais toucher la colonne suivante.
        c.drawString(margin + 54 * mm, y, _fit(c, e["type"], "Helvetica", 8.5, 62 * mm))
        c.drawString(margin + 120 * mm, y, e["carnet"][:16])
        c.setFillColor(BRAND_GREEN if e["sens"] == "+" else BAD)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(width - margin, y, f"{e['sens']} {_fmt_xaf(e['montant'])} XAF")
        y -= 13

    if not data["entries"]:
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(margin + 2, y, "Aucune écriture pour le moment.")

    # ── Totaux par produit (crédité / débité / net) ────────────────────────
    if data["entries"]:
        credits: dict[str, Decimal] = {}
        debits: dict[str, Decimal] = {}
        for e in data["entries"]:
            bucket = credits if e["sens"] == "+" else debits
            bucket[e["produit"]] = bucket.get(e["produit"], Decimal("0")) + e["montant"]

        # Réserve de place pour le bloc (titre + jusqu'à 2 lignes) ; sinon page.
        if y < 42 * mm:
            _footer(c, width, margin)
            c.showPage()
            y = _brand_header(
                c, width, height, margin,
                "RELEVÉ DES ÉCRITURES (SUITE)",
                f"{member.prenom} {member.nom} · {member.numero_membre}",
            )

        y -= 6
        c.setStrokeColor(PANEL_BORDER)
        c.setLineWidth(0.5)
        c.line(margin, y, width - margin, y)
        y -= 14
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(margin + 2, y, "TOTAUX PAR PRODUIT")
        y -= 14
        for prod in ("Collecte", "Classique"):
            cr = credits.get(prod, Decimal("0"))
            db = debits.get(prod, Decimal("0"))
            if cr == 0 and db == 0:
                continue
            net = cr - db
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(margin + 2, y, prod)
            c.setFillColor(BRAND_GREEN)
            c.setFont("Helvetica", 8.5)
            c.drawString(margin + 26 * mm, y, f"Crédité + {_fmt_xaf(cr)} XAF")
            c.setFillColor(BAD)
            c.drawString(margin + 78 * mm, y, f"Débité − {_fmt_xaf(db)} XAF")
            c.setFillColor(BRAND_GREEN if net >= 0 else BAD)
            c.setFont("Helvetica-Bold", 9)
            sign = "+" if net >= 0 else "−"
            c.drawRightString(
                width - margin, y, f"Net {sign} {_fmt_xaf(abs(net))} XAF",
            )
            y -= 13

    _footer(c, width, margin)
    c.showPage()
    c.save()
    return buf.getvalue()
