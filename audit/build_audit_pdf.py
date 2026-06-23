"""Generation du rapport d'audit Gathe Finance en PDF formel.

Style :
  - Pas de traits horizontaux (le user n'en veut pas)
  - Couvertures et entetes paginees
  - Tableaux propres en gris/bleu
  - Typographie sobre, gros titres, hierarchie claire
  - Palette inspiree du logo (bleu institutionnel + vert accent)

Sortie : audit/AUDIT_DEPLOIEMENT_2026-06-23.pdf
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# --- Palette institutionnelle Horus-lab -----------------------------------
NAVY = colors.HexColor("#0E2A47")      # bleu profond — titres
BLUE = colors.HexColor("#1E5FA8")      # bleu d'accent
SLATE = colors.HexColor("#37424A")     # gris ardoise — corps
MUTED = colors.HexColor("#6B7682")     # gris secondaire
SOFT_GREY = colors.HexColor("#E9ECEF") # bandeaux et tables
LIGHT_GREY = colors.HexColor("#F5F6F7")
GREEN_OK = colors.HexColor("#1A7F4F")  # statut OK
ORANGE_WARN = colors.HexColor("#C97E20")
RED_KO = colors.HexColor("#B0392F")
INFO_BLUE = colors.HexColor("#4A6FA5")

PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 28 * mm
MARGIN_B = 22 * mm


# --- Page templates avec entete + pied de page -----------------------------
def header_footer(canv: canvas.Canvas, doc: BaseDocTemplate) -> None:
    """En-tete et pied de page repetes sur chaque page interieure."""
    canv.saveState()
    # Bandeau header (filet horizontal supprime — juste texte align)
    canv.setFont("Helvetica-Bold", 8)
    canv.setFillColor(NAVY)
    canv.drawString(MARGIN_L, PAGE_H - 18 * mm, "GROUPE HORUS-LAB")
    canv.setFont("Helvetica", 8)
    canv.setFillColor(MUTED)
    canv.drawString(MARGIN_L + 35 * mm, PAGE_H - 18 * mm,
                    "Cellule Audit & Recette")
    canv.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 18 * mm,
                         "AUDIT-GF-2026-06-23-DEP")

    # Filet vertical subtile a gauche (motif "manuel")
    canv.setStrokeColor(BLUE)
    canv.setLineWidth(2)
    canv.line(MARGIN_L - 6 * mm, MARGIN_B + 8 * mm,
              MARGIN_L - 6 * mm, PAGE_H - MARGIN_T + 5 * mm)

    # Pied de page : titre + numero
    canv.setFont("Helvetica", 8)
    canv.setFillColor(MUTED)
    canv.drawString(MARGIN_L, MARGIN_B - 8 * mm,
                    "Audit de deploiement — Gathe Finance — 23 juin 2026")
    canv.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 8 * mm,
                         f"Page {canv.getPageNumber()}")
    canv.restoreState()


def cover_page(canv: canvas.Canvas, doc: BaseDocTemplate) -> None:
    """Couverture sobre, sans trait horizontal."""
    canv.saveState()
    # Bandeau navy en haut (filet decoratif vertical a droite + texte)
    canv.setFillColor(NAVY)
    canv.rect(0, PAGE_H - 80 * mm, PAGE_W, 80 * mm, stroke=0, fill=1)

    # Filet vert d'accent
    canv.setFillColor(GREEN_OK)
    canv.rect(MARGIN_L, PAGE_H - 90 * mm, 25 * mm, 4 * mm, stroke=0, fill=1)

    # Titre
    canv.setFillColor(colors.white)
    canv.setFont("Helvetica-Bold", 11)
    canv.drawString(MARGIN_L, PAGE_H - 30 * mm, "GROUPE HORUS-LAB")
    canv.setFont("Helvetica", 9)
    canv.drawString(MARGIN_L, PAGE_H - 36 * mm,
                    "Cellule Audit & Recette  •  Douala, Cameroun")

    canv.setFont("Helvetica-Bold", 28)
    canv.drawString(MARGIN_L, PAGE_H - 56 * mm,
                    "Rapport d’audit de deploiement")

    canv.setFont("Helvetica", 14)
    canv.drawString(MARGIN_L, PAGE_H - 67 * mm,
                    "Plateforme cooperative Gathe Finance")

    # Metadonnees en bas
    canv.setFillColor(SLATE)
    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 105 * mm, "Reference")
    canv.setFont("Helvetica", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 105 * mm,
                    "AUDIT-GF-2026-06-23-DEP")

    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 112 * mm, "Date d’emission")
    canv.setFont("Helvetica", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 112 * mm, "23 juin 2026")

    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 119 * mm, "Type d’audit")
    canv.setFont("Helvetica", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 119 * mm,
                    "Post-deploiement  —  Infrastructure & Applicatif")

    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 126 * mm, "Perimetre")
    canv.setFont("Helvetica", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 126 * mm,
                    "5 sous-domaines + application mobile Flutter")

    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 133 * mm, "Environnement")
    canv.setFont("Helvetica", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 133 * mm,
                    "VPS Contabo  —  gathe-finance.horus-lab.com")

    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L, PAGE_H - 140 * mm, "Niveau de risque")
    canv.setFillColor(ORANGE_WARN)
    canv.setFont("Helvetica-Bold", 10)
    canv.drawString(MARGIN_L + 32 * mm, PAGE_H - 140 * mm,
                    "Operationnel avec 4 reserves bloquantes")

    # Cadre verdict en bas
    canv.setFillColor(LIGHT_GREY)
    canv.rect(MARGIN_L, MARGIN_B + 10 * mm,
              PAGE_W - MARGIN_L - MARGIN_R, 50 * mm,
              stroke=0, fill=1)
    canv.setFillColor(NAVY)
    canv.setFont("Helvetica-Bold", 11)
    canv.drawString(MARGIN_L + 6 * mm, MARGIN_B + 52 * mm,
                    "VERDICT GLOBAL")
    canv.setFillColor(SLATE)
    canv.setFont("Helvetica", 10)
    txt = [
        "La stack Gathe Finance est techniquement deployee et joignable en HTTPS",
        "sur les cinq sous-domaines audites. Le moteur metier Django ainsi que la",
        "base Postgres sont sains. Quatre points bloquants UX ont neanmoins ete",
        "identifies, dont l’erreur HTTP 400 sur la console d’administration",
        "qui doit etre traitee en priorite avant ouverture grand public.",
    ]
    y = MARGIN_B + 42 * mm
    for line in txt:
        canv.drawString(MARGIN_L + 6 * mm, y, line)
        y -= 5 * mm

    # Footer cover
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica", 8)
    canv.drawString(MARGIN_L, MARGIN_B - 8 * mm,
                    "Document confidentiel  •  Diffusion restreinte aux equipes Dev / Ops")
    canv.restoreState()


# --- Styles texte ---------------------------------------------------------
def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles = {
        "H1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontName="Helvetica-Bold", fontSize=20, leading=24,
            textColor=NAVY, spaceBefore=18, spaceAfter=8,
            keepWithNext=True,
        ),
        "H2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=14, leading=18,
            textColor=BLUE, spaceBefore=16, spaceAfter=4,
            keepWithNext=True,
        ),
        "H3": ParagraphStyle(
            "H3", parent=base["Heading3"],
            fontName="Helvetica-Bold", fontSize=11, leading=14,
            textColor=NAVY, spaceBefore=10, spaceAfter=2,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=SLATE, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "BodyLeft": ParagraphStyle(
            "BodyLeft", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=SLATE, spaceAfter=6, alignment=TA_LEFT,
        ),
        "Lead": ParagraphStyle(
            "Lead", parent=base["BodyText"],
            fontName="Helvetica", fontSize=11, leading=16,
            textColor=NAVY, spaceAfter=8,
        ),
        "Caption": ParagraphStyle(
            "Caption", parent=base["BodyText"],
            fontName="Helvetica-Oblique", fontSize=9, leading=12,
            textColor=MUTED, spaceAfter=6,
        ),
        "Quote": ParagraphStyle(
            "Quote", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=NAVY, leftIndent=10, rightIndent=10,
            spaceBefore=6, spaceAfter=6, alignment=TA_LEFT,
            backColor=LIGHT_GREY, borderPadding=8,
        ),
        "Bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"],
            fontName="Helvetica", fontSize=10, leading=14,
            textColor=SLATE, leftIndent=12, bulletIndent=0,
            spaceAfter=3,
        ),
        "TableHdr": ParagraphStyle(
            "TableHdr", fontName="Helvetica-Bold", fontSize=9.5,
            textColor=colors.white, leading=12, alignment=TA_LEFT,
        ),
        "TableCell": ParagraphStyle(
            "TableCell", fontName="Helvetica", fontSize=9,
            textColor=SLATE, leading=12, alignment=TA_LEFT,
        ),
        "TableCellBold": ParagraphStyle(
            "TableCellBold", fontName="Helvetica-Bold", fontSize=9,
            textColor=NAVY, leading=12, alignment=TA_LEFT,
        ),
        "Code": ParagraphStyle(
            "Code", fontName="Courier", fontSize=8.5, leading=11,
            textColor=NAVY, leftIndent=8, spaceAfter=6,
        ),
        "Mono": ParagraphStyle(
            "Mono", fontName="Courier", fontSize=9, leading=11,
            textColor=SLATE, alignment=TA_LEFT,
        ),
    }
    return styles


# --- Composants reutilisables ---------------------------------------------
def section_band(title: str, styles: dict[str, ParagraphStyle]):
    """Bandeau de section : titre sur fond clair, sans trait horizontal."""
    tbl = Table(
        [[Paragraph(f"<b>{title}</b>", styles["H1"])]],
        colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
        rowHeights=[14 * mm],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT_GREY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def info_box(label: str, body: str, styles: dict[str, ParagraphStyle],
             color: colors.Color = BLUE):
    """Encart d'information : barre verticale colored + texte."""
    body_par = Paragraph(body, styles["BodyLeft"])
    label_par = Paragraph(f"<b>{label}</b>", styles["H3"])
    tbl = Table(
        [[label_par], [body_par]],
        colWidths=[PAGE_W - MARGIN_L - MARGIN_R],
    )
    tbl.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 3, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (0, 0), 4),
        ("BOTTOMPADDING", (0, 0), (0, 0), 0),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
    ]))
    return KeepTogether([tbl, Spacer(1, 4 * mm)])


def styled_table(data, col_widths, styles: dict[str, ParagraphStyle],
                 first_col_bold: bool = False):
    """Tableau formel : header navy, lignes alternees, sans bordures noires."""
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT")
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9.5),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, NAVY),
    ]
    # Lignes alternees
    for i in range(1, len(data)):
        if i % 2 == 1:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), LIGHT_GREY))
    if first_col_bold:
        style_cmds.append(("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"))
        style_cmds.append(("TEXTCOLOR", (0, 1), (0, -1), NAVY))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def severity_chip(level: str) -> Paragraph:
    palette = {
        "CRITIQUE": (RED_KO, colors.white),
        "MAJEUR": (ORANGE_WARN, colors.white),
        "MINEUR": (colors.HexColor("#E8C45C"), NAVY),
        "INFO": (INFO_BLUE, colors.white),
    }
    bg, fg = palette.get(level.upper(), (MUTED, colors.white))
    return Paragraph(
        f'<font color="{fg.hexval()}"><b> {level} </b></font>',
        ParagraphStyle(
            "Sev", fontName="Helvetica-Bold", fontSize=8.5,
            backColor=bg, textColor=fg, leading=11,
            borderPadding=3, alignment=TA_CENTER,
        ),
    )


# --- Contenu du document --------------------------------------------------
def build_story(styles: dict[str, ParagraphStyle]):
    story: list = []

    # --- Page 1 : couverture (rendue par cover_page canvas) ---
    story.append(PageBreak())

    # --- Sommaire ---
    story.append(section_band("Sommaire", styles))
    story.append(Spacer(1, 4 * mm))
    toc = [
        ("01", "Synthese executive"),
        ("02", "Methodologie de l’audit"),
        ("03", "Perimetre evalue"),
        ("04", "Synthese des constats"),
        ("05", "Detail par plateforme"),
        ("06", "Infrastructure et exploitation"),
        ("07", "Findings classes par severite"),
        ("08", "Plan de remediation recommande"),
        ("09", "Annexes techniques"),
    ]
    toc_data = [
        [Paragraph(f'<font color="{BLUE.hexval()}"><b>{n}</b></font>',
                   styles["TableCellBold"]),
         Paragraph(t, styles["TableCell"])]
        for n, t in toc
    ]
    toc_tbl = Table(toc_data, colWidths=[18 * mm, 140 * mm])
    toc_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(toc_tbl)
    story.append(PageBreak())

    # =========== 01 SYNTHESE EXECUTIVE ===========
    story.append(section_band("01. Synthese executive", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Contexte de la mission", styles["H2"]))
    story.append(Paragraph(
        "Le <b>Groupe Horus-lab</b>, agissant en qualite d’auditeur "
        "independant a la demande de la direction technique de la cooperative "
        "Gathe Finance, a procede le <b>23 juin 2026</b> au controle complet "
        "de la stack de production fraichement deployee sur le VPS Contabo "
        "<font face=\"Courier\">81.0.246.144</font>. L’objectif etait de "
        "valider l’operationnabilite reelle des cinq plateformes "
        "publiques ainsi que du client mobile Flutter, et de produire un "
        "etat des lieux exploitable par les equipes Dev et Ops avant "
        "ouverture grand public.",
        styles["Body"],
    ))

    story.append(Paragraph("Verdict global", styles["H2"]))
    story.append(Paragraph(
        "La stack est <b>techniquement deployee et joignable</b> en HTTPS "
        "sur les cinq sous-domaines audites. Le moteur metier Django ainsi "
        "que la base Postgres sont reportes en etat <i>healthy</i>. Quatre "
        "irritants bloquants pour l’experience utilisateur ont neanmoins "
        "ete identifies, dont une erreur HTTP&nbsp;400 sur la console "
        "d’administration qui doit imperativement etre traitee avant "
        "l’ouverture aux operateurs staff.",
        styles["Body"],
    ))

    # Tableau indicateurs
    story.append(Paragraph("Indicateurs cles", styles["H2"]))
    story.append(Spacer(1, 2 * mm))
    indicators = [
        ["Indicateur", "Statut", "Commentaire"],
        ["Disponibilite reseau", "OK", "Cinq sous-domaines repondent en HTTPS valide"],
        ["Validite certificats TLS", "OK", "Let’s Encrypt actifs sur tous les vhosts"],
        ["Sante backend Django", "OK", "Healthcheck /healthz/ = 200, conteneur healthy"],
        ["Sante Postgres 16", "OK", "DB initialisee, conteneur healthy"],
        ["Routage nginx mutualise", "OK", "Quatre projets en cohabitation propre"],
        ["UX console admin", "RESERVE", "Erreur HTTP 400 sur l’API rewrite"],
        ["UX portail membre", "RESERVE", "Routes non prefixees retournent 404"],
        ["CMS Wagtail (racine cms.*)", "RESERVE", "Redirige silencieusement vers la vitrine"],
        ["Build mobile production (AAB)", "OK", "Signe, 53,7 Mo, pret Play Store"],
        ["Suite de tests mobile", "OK", "118 / 118 tests verts"],
        ["Pipeline CI/CD GHCR", "OK", "Workflows ci.yml + deploy.yml armes"],
    ]
    tbl_ind = styled_table(
        indicators,
        col_widths=[55 * mm, 25 * mm, 86 * mm],
        styles=styles,
    )
    # Coloration de la colonne statut
    style_extra = []
    for i, row in enumerate(indicators[1:], start=1):
        if row[1] == "OK":
            style_extra.append(("TEXTCOLOR", (1, i), (1, i), GREEN_OK))
            style_extra.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
        elif row[1] == "RESERVE":
            style_extra.append(("TEXTCOLOR", (1, i), (1, i), ORANGE_WARN))
            style_extra.append(("FONTNAME", (1, i), (1, i), "Helvetica-Bold"))
    tbl_ind.setStyle(TableStyle(style_extra))
    story.append(tbl_ind)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph(
        "Score consolide : <b>huit indicateurs verts sur onze</b>. "
        "L’audit qualifie la mise en service de <i>reussie avec "
        "reserves a lever</i>.",
        styles["Caption"],
    ))

    # Faits saillants
    story.append(Paragraph("Faits saillants", styles["H2"]))
    bullets = [
        "Mise en service technique reussie : les images GHCR sont deployees, "
        "les certificats Let’s Encrypt emis et les services socle "
        "joignables.",
        "Quatre irritants UX bloquent un parcours utilisateur fluide ; ils "
        "sont concentres sur la console admin et le portail membre.",
        "Trois actions tierces restent a executer par l’exploitant : "
        "declaration du webhook Tara, verification du domaine expediteur "
        "Brevo, publication de l’AAB sur Google Play Console.",
        "Aucune vulnerabilite critique ni perte de donnees imminente "
        "detectee dans le perimetre de cet audit externe.",
    ]
    for b in bullets:
        story.append(Paragraph(
            f"<font color=\"{BLUE.hexval()}\">•</font> &nbsp; {b}",
            styles["Bullet"],
        ))

    story.append(PageBreak())

    # =========== 02 METHODOLOGIE ===========
    story.append(section_band("02. Methodologie de l’audit", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Approche retenue", styles["H2"]))
    story.append(Paragraph(
        "L’audit a ete conduit en <b>boite grise</b>, combinant des "
        "controles externes par requetes HTTP/S, l’inspection des "
        "fichiers d’infrastructure (docker-compose, configurations "
        "nginx, variables d’environnement anonymisees) et la lecture "
        "ciblee du code applicatif Next.js, Django et Flutter pour mettre "
        "en regard les comportements observes avec les chemins "
        "d’execution sous-jacents.",
        styles["Body"],
    ))

    story.append(Paragraph("Operations realisees", styles["H2"]))
    ops = [
        "Sondage HTTP de chaque sous-domaine (codes retour, en-tetes, "
        "redirections, taille de payload, temps de reponse).",
        "Inspection des conteneurs Docker en production et de leurs "
        "configurations runtime (variables d’environnement, "
        "reseaux, alias DNS).",
        "Lecture des fichiers <font face=\"Courier\">docker-compose.prod.yml</font>, "
        "<font face=\"Courier\">docker-compose.nginx-external.yml</font>, "
        "des settings Django de production et de la configuration nginx "
        "mutualisee.",
        "Execution complete de la suite de tests Flutter "
        "(<font face=\"Courier\">flutter test</font>) ainsi que de "
        "l’analyseur statique "
        "(<font face=\"Courier\">flutter analyze</font>).",
        "Production d’un build AAB de production avec injection de "
        "l’URL prod dans la configuration mobile.",
    ]
    for op in ops:
        story.append(Paragraph(
            f"<font color=\"{BLUE.hexval()}\">▸</font> &nbsp; {op}",
            styles["Bullet"],
        ))

    story.append(Paragraph("Criteres d’evaluation", styles["H2"]))
    story.append(Spacer(1, 2 * mm))
    criteria = [
        ["Dimension", "Question controlee"],
        ["Disponibilite", "L’URL repond-elle en HTTPS valide ?"],
        ["Contenu rendu", "Le HTML ou JSON livre correspond-il a l’attendu fonctionnel ?"],
        ["Coherence routage", "Les routes alternatives (locales, sous-pages cles) renvoient-elles 200 ?"],
        ["UX premier acces", "Un visiteur non-authentifie obtient-il un etat utilisable ?"],
    ]
    story.append(styled_table(
        criteria, col_widths=[45 * mm, 121 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Limites declarees", styles["H2"]))
    limits = [
        "Les controles fonctionnels metier (versement, demande de credit, "
        "decision comite, webhook Tara) n’ont pas ete rejoues end-to-end, "
        "faute de compte membre actif en production.",
        "Les logs runtime cote serveur ont repose sur les retours de "
        "l’exploitant : l’auditeur n’a pas eu d’acces "
        "SSH direct durant la mission.",
        "Les tests de charge et l’etude de resilience sont hors perimetre.",
    ]
    for ln in limits:
        story.append(Paragraph(
            f"<font color=\"{MUTED.hexval()}\">—</font> &nbsp; {ln}",
            styles["Bullet"],
        ))

    story.append(PageBreak())

    # =========== 03 PERIMETRE ===========
    story.append(section_band("03. Perimetre evalue", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Plateformes audites", styles["H2"]))
    story.append(Spacer(1, 2 * mm))
    perim = [
        ["#", "Sous-domaine", "Role", "Image"],
        ["1", "gathe-finance.horus-lab.com", "Vitrine publique Next.js",
         "ghcr.io/…/site:latest"],
        ["2", "portail.gathe-finance.horus-lab.com", "Espace membre Next.js",
         "ghcr.io/…/portal:latest"],
        ["3", "admin.gathe-finance.horus-lab.com", "Console staff Next.js",
         "ghcr.io/…/admin:latest"],
        ["4", "api.gathe-finance.horus-lab.com", "API REST Django + DRF",
         "ghcr.io/…/backend:latest"],
        ["5", "cms.gathe-finance.horus-lab.com", "Wagtail — edition contenu",
         "ghcr.io/…/backend:latest"],
    ]
    story.append(styled_table(
        perim, col_widths=[10 * mm, 60 * mm, 50 * mm, 46 * mm], styles=styles,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Services tiers branches", styles["H2"]))
    story.append(Spacer(1, 2 * mm))
    tiers = [
        ["Service", "Etat", "Action requise"],
        ["Brevo (e-mails transactionnels)", "Configure",
         "Verifier domaine expediteur dans la console Brevo"],
        ["Tara MoMo (paiements)", "Configure",
         "Declarer l’URL de webhook dans le dashboard Tara"],
        ["GitHub Container Registry", "Pipeline actif",
         "Quatre images publiees a chaque push sur main"],
        ["Let’s Encrypt", "Cinq certificats actifs",
         "Renouvellement automatique par certbot"],
        ["Google Play Console", "AAB pret",
         "Upload manuel restant a executer"],
    ]
    story.append(styled_table(
        tiers, col_widths=[55 * mm, 35 * mm, 76 * mm], styles=styles,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Topologie d’infrastructure", styles["H2"]))
    story.append(Paragraph(
        "La cible heberge actuellement <b>quatre projets independants</b> "
        "derriere un meme reverse-proxy nginx mutualise. Les conteneurs "
        "Gathe Finance rejoignent le reseau Docker partage et y exposent "
        "des alias DNS uniques (<font face=\"Courier\">gathe-backend</font>, "
        "<font face=\"Courier\">gathe-db</font>, "
        "<font face=\"Courier\">gathe-site</font>, etc.) qui evitent les "
        "collisions de noms avec les autres projets.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # =========== 04 SYNTHESE DES CONSTATS ===========
    story.append(section_band("04. Synthese des constats", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Carte de chaleur des plateformes", styles["H2"]))
    story.append(Spacer(1, 2 * mm))
    heat = [
        ["Plateforme", "Disponibilite", "Contenu", "Routage", "UX", "Note"],
        ["Vitrine publique", "OK", "OK", "OK", "OK", "A"],
        ["Portail membre", "OK", "OK", "RESERVE", "OK", "B"],
        ["Console admin", "OK", "RESERVE", "RESERVE", "RESERVE", "C+"],
        ["API REST", "OK", "OK", "OK", "OK", "A"],
        ["CMS Wagtail", "OK", "RESERVE", "RESERVE", "RESERVE", "B−"],
        ["Mobile (build)", "OK", "OK", "OK", "OK", "A"],
    ]
    tbl_heat = styled_table(
        heat, col_widths=[40 * mm, 28 * mm, 22 * mm, 22 * mm, 22 * mm, 18 * mm],
        styles=styles, first_col_bold=True,
    )
    extra = []
    for i, row in enumerate(heat[1:], start=1):
        for j in range(1, 5):
            if row[j] == "OK":
                extra.append(("TEXTCOLOR", (j, i), (j, i), GREEN_OK))
                extra.append(("FONTNAME", (j, i), (j, i), "Helvetica-Bold"))
            else:
                extra.append(("TEXTCOLOR", (j, i), (j, i), ORANGE_WARN))
                extra.append(("FONTNAME", (j, i), (j, i), "Helvetica-Bold"))
        # Note column color
        note_color = {
            "A": GREEN_OK, "B": ORANGE_WARN,
            "C+": RED_KO, "B−": ORANGE_WARN,
        }.get(row[5], SLATE)
        extra.append(("TEXTCOLOR", (5, i), (5, i), note_color))
        extra.append(("FONTNAME", (5, i), (5, i), "Helvetica-Bold"))
    tbl_heat.setStyle(TableStyle(extra))
    story.append(tbl_heat)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Quatre irritants prioritaires", styles["H2"]))

    story.append(info_box(
        "F-01 — MAJEUR — Console d’administration",
        "La page <font face=\"Courier\">/dashboard</font> renvoie une erreur "
        "<b>HTTP 400 Bad Request</b> sur les appels API client-side. Le rewrite "
        "Next.js qui proxifie <font face=\"Courier\">/api/v1/*</font> vers "
        "<font face=\"Courier\">gathe-backend:8000</font> est rejete par Django. "
        "Resultat : page blanche apres le shell de chargement.",
        styles, ORANGE_WARN,
    ))

    story.append(info_box(
        "F-02 — MAJEUR — Console d’administration",
        "Lorsqu’un visiteur non authentifie atteint la racine "
        "<font face=\"Courier\">/</font>, l’application redirige vers "
        "<font face=\"Courier\">/dashboard</font> et reste figee sur l’etat "
        "<i>Chargement…</i>. Aucune bascule automatique vers "
        "<font face=\"Courier\">/login</font> n’est declenchee.",
        styles, ORANGE_WARN,
    ))

    story.append(info_box(
        "F-03 — MAJEUR — Portail membre",
        "Les routes non prefixees telles que "
        "<font face=\"Courier\">/login</font> ou "
        "<font face=\"Courier\">/dashboard</font> retournent un 404. Seules "
        "les URL prefixees par la locale "
        "(<font face=\"Courier\">/fr/…</font>, "
        "<font face=\"Courier\">/en/…</font>) sont resolues. Les liens "
        "transactionnels emis par e-mail sont donc fragiles.",
        styles, ORANGE_WARN,
    ))

    story.append(info_box(
        "F-04 — MINEUR — CMS Wagtail",
        "La racine <font face=\"Courier\">cms.gathe-finance.horus-lab.com/</font> "
        "redirige silencieusement vers la vitrine. Le sous-domaine devrait "
        "afficher un message d’orientation ou rediriger directement vers "
        "<font face=\"Courier\">/admin/</font>.",
        styles, INFO_BLUE,
    ))

    story.append(PageBreak())

    # =========== 05 DETAIL PAR PLATEFORME ===========
    story.append(section_band("05. Detail par plateforme", styles))
    story.append(Spacer(1, 4 * mm))

    # 5.1 Vitrine
    story.append(Paragraph(
        "5.1  Vitrine publique  —  "
        "<font color=\"#1A7F4F\">CONFORME</font>", styles["H2"]))
    story.append(Paragraph(
        "<b>URL auditee :</b> https://gathe-finance.horus-lab.com/",
        styles["Caption"],
    ))
    vit = [
        ["Parametre", "Valeur observee"],
        ["Code HTTP", "200 OK"],
        ["Titre HTML", "Gathe Finance — Cooperative d’epargne et de credit au Cameroun"],
        ["Poids HTML", "197 942 octets"],
        ["Temps de reponse", "1,73 seconde (cold)"],
        ["En-tete Server", "nginx/1.29.8"],
        ["TLS", "Let’s Encrypt valide"],
    ]
    story.append(styled_table(
        vit, col_widths=[40 * mm, 126 * mm], styles=styles, first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Le rendu Next.js est complet, les polices Sora et Inter sont "
        "pre-chargees, les images optimisees via le pipeline "
        "<font face=\"Courier\">_next/image</font>. La locale FR est "
        "detectee et le contenu institutionnel est coherent avec "
        "l’identite visuelle de la cooperative. <b>Aucune reserve.</b>",
        styles["Body"],
    ))

    # 5.2 Portail
    story.append(Paragraph(
        "5.2  Portail membre  —  "
        "<font color=\"#C97E20\">CONFORME PARTIELLEMENT</font>",
        styles["H2"]))
    story.append(Paragraph(
        "<b>URL auditee :</b> https://portail.gathe-finance.horus-lab.com/",
        styles["Caption"],
    ))
    por = [
        ["Endpoint", "Code", "Statut"],
        ["GET /", "200", "OK"],
        ["GET /fr", "200", "OK"],
        ["GET /login", "404", "Non resolu (non prefixe)"],
        ["GET /dashboard", "404", "Non resolu (non prefixe)"],
    ]
    story.append(styled_table(
        por, col_widths=[55 * mm, 25 * mm, 86 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Toutes les routes fonctionnelles vivent sous "
        "<font face=\"Courier\">/[locale]/…</font>. Les chemins non "
        "prefixes (<font face=\"Courier\">/login</font>, "
        "<font face=\"Courier\">/dashboard</font>, "
        "<font face=\"Courier\">/savings</font>, "
        "<font face=\"Courier\">/loans</font>) retournent 404 "
        "systematiquement. L’origine probable est l’absence de "
        "fallback dans le middleware "
        "<font face=\"Courier\">next-intl</font>. Impact metier : les "
        "e-mails transactionnels (welcome, decaissement, retrait) qui "
        "contiennent des liens non prefixes echoueront silencieusement.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # 5.3 Admin
    story.append(Paragraph(
        "5.3  Console d’administration  —  "
        "<font color=\"#B0392F\">NON CONFORME</font>",
        styles["H2"]))
    story.append(Paragraph(
        "<b>URL auditee :</b> https://admin.gathe-finance.horus-lab.com/  "
        "&nbsp;&nbsp; <i>Plateforme la plus degradee.</i>",
        styles["Caption"],
    ))
    adm = [
        ["Endpoint", "Code", "Statut"],
        ["GET /", "200", "Redirige en interne vers /dashboard"],
        ["GET /dashboard", "200", "Page blanche — erreur 400 au fetch API"],
        ["GET /login", "200", "Formulaire rendu correctement"],
        ["GET /fr", "404", "Pas d’i18n cote admin"],
        ["GET /api/v1/admin/dashboard/", "400", "Rewrite Next.js rejete par Django"],
    ]
    story.append(styled_table(
        adm, col_widths=[60 * mm, 25 * mm, 81 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "<b>Analyse de la cause technique.</b> La console d’administration "
        "Next.js utilise un client API en chemin relatif "
        "(<font face=\"Courier\">const API_BASE = \"/api/v1\"</font>) et "
        "repose sur une regle "
        "<font face=\"Courier\">rewrites()</font> du "
        "<font face=\"Courier\">next.config.mjs</font> qui proxifie "
        "<font face=\"Courier\">/api/v1/:path+</font> vers "
        "<font face=\"Courier\">${BACKEND_INTERNAL_URL}/api/v1/:path+/</font>. "
        "En production, le backend repond systematiquement par un "
        "<b>HTTP 400 Bad Request</b> au flux passant par ce rewrite, alors "
        "que la meme requete envoyee directement a "
        "<font face=\"Courier\">api.gathe-finance.horus-lab.com</font> "
        "retourne un 403 attendu (auth requise).",
        styles["Body"],
    ))

    story.append(Paragraph(
        "<b>Hypothese privilegiee.</b> Le rewrite Node forge un en-tete "
        "<font face=\"Courier\">Host: gathe-backend</font> qui n’est "
        "pas reconnu par <font face=\"Courier\">DJANGO_ALLOWED_HOSTS</font> "
        "dans l’environnement runtime du conteneur, soit parce que "
        "l’override "
        "<font face=\"Courier\">docker-compose.nginx-external.yml</font> "
        "n’a pas applique sa concatenation au moment du redemarrage, "
        "soit parce que <font face=\"Courier\">CSRF_TRUSTED_ORIGINS</font> "
        "ne contient pas <font face=\"Courier\">admin.gathe-finance.horus-lab.com</font>. "
        "La verification est consignee au point F-01 du plan de remediation.",
        styles["Body"],
    ))

    story.append(Paragraph(
        "<b>Impact metier.</b> Un operateur staff qui tape directement "
        "l’URL admin dans son navigateur voit un ecran de chargement "
        "puis une page blanche. Le seul recours actuel est de deviner "
        "l’URL <font face=\"Courier\">/login</font>, ce qui sera "
        "percu comme un blocage applicatif majeur lors de la formation "
        "des operateurs.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # 5.4 API
    story.append(Paragraph(
        "5.4  API REST  —  "
        "<font color=\"#1A7F4F\">CONFORME</font>",
        styles["H2"]))
    story.append(Paragraph(
        "<b>URL auditee :</b> https://api.gathe-finance.horus-lab.com",
        styles["Caption"],
    ))
    api = [
        ["Endpoint", "Methode", "Code", "Statut"],
        ["/healthz/", "GET", "200", "Healthcheck OK"],
        ["/api/v1/savings/info/", "GET", "200", "Payload JSON conforme"],
        ["/api/v1/auth/login/", "POST", "400", "Message FR : Email et mot de passe requis"],
        ["/api/v1/auth/login/", "GET", "405", "Method not allowed attendu"],
        ["/api/v1/members/me/", "GET (anonyme)", "403", "Auth requise"],
    ]
    story.append(styled_table(
        api, col_widths=[55 * mm, 28 * mm, 18 * mm, 65 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Le backend Django repond rapidement, retourne des messages "
        "d’erreur en francais et fournit un payload JSON conforme aux "
        "regles metier 2026 (montant suggere 1&nbsp;000&nbsp;XAF, cut-off 17h, "
        "canal Tara primaire). Le conteneur "
        "<font face=\"Courier\">gathe-finance-prod-backend-1</font> est marque "
        "<i>healthy</i>. La base Postgres a ete reinitialisee proprement "
        "apres reset du mot de passe et accueille un schema migre complet.",
        styles["Body"],
    ))

    # 5.5 CMS
    story.append(Paragraph(
        "5.5  CMS Wagtail  —  "
        "<font color=\"#C97E20\">CONFORME PARTIELLEMENT</font>",
        styles["H2"]))
    cms = [
        ["Endpoint", "Code", "Statut"],
        ["/", "302 vers vitrine", "Comportement non desire"],
        ["/admin/", "200", "Console accessible (S’identifier — Wagtail)"],
        ["/api/v2/pages/", "200", "API headless OK"],
        ["/cms/admin/", "404", "Normal (chemin inutile)"],
    ]
    story.append(styled_table(
        cms, col_widths=[40 * mm, 38 * mm, 88 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "La console Wagtail est accessible sous "
        "<font face=\"Courier\">/admin/</font>, le formulaire "
        "d’authentification s’affiche correctement, et l’API "
        "headless <font face=\"Courier\">/api/v2/pages/</font> est exploitable "
        "par les fronts Next.js et mobile. La racine du sous-domaine "
        "redirige cependant silencieusement vers la vitrine, ce qui est un "
        "signal de deploiement non finalise. Recommandation : afficher une "
        "page d’orientation explicite ou rediriger vers "
        "<font face=\"Courier\">/admin/</font>.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # 5.6 Mobile
    story.append(Paragraph(
        "5.6  Application mobile Flutter  —  "
        "<font color=\"#1A7F4F\">CONFORME ET LIVRABLE</font>",
        styles["H2"]))
    story.append(Paragraph(
        "Build de production execute le 23 juin 2026 sur le poste de "
        "l’auditeur, base sur la branche <font face=\"Courier\">main</font> "
        "deployee.",
        styles["Caption"],
    ))
    mob = [
        ["Indicateur", "Resultat"],
        ["flutter pub get", "Succes"],
        ["flutter analyze", "62 infos/warnings toleres, 0 erreur fatale"],
        ["flutter test", "118 / 118 tests verts"],
        ["Build AAB release", "app-release.aab, 53,7 Mo"],
        ["Signature", "gathefinance-upload.jks valide"],
        ["API_BASE_URL grave", "https://api.gathe-finance.horus-lab.com"],
    ]
    story.append(styled_table(
        mob, col_widths=[55 * mm, 111 * mm], styles=styles, first_col_bold=True,
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "La configuration <font face=\"Courier\">ApiConfig.baseUrl</font> est "
        "injectable via <font face=\"Courier\">--dart-define</font> a la "
        "compilation, sans modification de source. Le binaire AAB est pret "
        "pour upload sur la console Google Play. La suite de tests couvre "
        "l’authentification, l’epargne, le credit, les paiements, "
        "les notifications, le profil, l’onboarding et le PIN. Les "
        "soixante-deux remontees de l’analyseur statique sont des "
        "<font face=\"Courier\">unawaited_futures</font>, des "
        "<font face=\"Courier\">trailing_commas</font> manquantes et un "
        "<font face=\"Courier\">unused_import</font>. Aucune n’est "
        "bloquante mais un <i>sweep</i> dedie est recommande.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # =========== 06 INFRASTRUCTURE ===========
    story.append(section_band("06. Infrastructure et exploitation", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("6.1  Caracteristiques de l’hote", styles["H2"]))
    host = [
        ["Parametre", "Valeur"],
        ["Fournisseur", "Contabo"],
        ["Adresse IP publique", "81.0.246.144"],
        ["Systeme d’exploitation", "Ubuntu 24.04.4 LTS"],
        ["Noyau", "6.8.0-106-generic"],
        ["Charge moyenne", "0,32 (sain)"],
        ["Utilisation disque", "51,7 % sur 95,82 Go"],
        ["Utilisation memoire", "49 %"],
    ]
    story.append(styled_table(
        host, col_widths=[55 * mm, 111 * mm], styles=styles, first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("6.2  Reverse-proxy mutualise", styles["H2"]))
    story.append(Paragraph(
        "Le conteneur <font face=\"Courier\">backend-nginx-1</font> "
        "(image <font face=\"Courier\">nginx:alpine</font>) sert "
        "simultanement <b>quatre projets independants</b>. Cette "
        "mutualisation impose une discipline forte sur les noms de service "
        "et les alias DNS du reseau Docker partage.",
        styles["Body"],
    ))
    coh = [
        ["Projet", "Sous-domaines", "Cohabitation"],
        ["afrikamode", "backend.afrikamode.horus-lab.com", "Active"],
        ["assistant-direction-api", "api-assistant-ia.horus-lab.com",
         "Retire — bloc nginx nettoye lors de l’audit"],
        ["edlearning", "edlearning.horus-lab.com", "Active"],
        ["Gathe Finance", "Cinq sous-domaines listes en 3.1", "Active"],
    ]
    story.append(styled_table(
        coh, col_widths=[40 * mm, 70 * mm, 56 * mm], styles=styles,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("6.3  Incident corrige en cours d’audit", styles["H2"]))
    story.append(Paragraph(
        "Au demarrage du conteneur nginx mutualise, l’erreur "
        "<font face=\"Courier\">[emerg] host not found in upstream "
        "“assistant-direction-api”</font> empechait le redemarrage. "
        "Le conteneur tiers avait ete retire sans nettoyage de la "
        "configuration nginx. <b>L’auditeur a fait supprimer les lignes "
        "140 a 199</b> du fichier "
        "<font face=\"Courier\">/home/deploy/afrikamode/backend/deploy/nginx/default.conf</font>, "
        "creant prealablement un <i>backup .bak</i>. Le redemarrage est "
        "valide, les quatre projets ont ete restaures dans le meme temps.",
        styles["Body"],
    ))

    story.append(Paragraph("6.4  Pipeline d’integration et de deploiement", styles["H2"]))
    story.append(Paragraph(
        "Deux workflows GitHub Actions sont armes. "
        "<font face=\"Courier\">ci.yml</font> execute les tests obligatoires "
        "(<font face=\"Courier\">ruff</font> et "
        "<font face=\"Courier\">pytest</font> backend, "
        "<font face=\"Courier\">npm lint</font> et "
        "<font face=\"Courier\">tsc</font> frontend, "
        "<font face=\"Courier\">flutter analyze</font> et "
        "<font face=\"Courier\">flutter test</font>) puis publie quatre "
        "images GHCR en parallele. "
        "<font face=\"Courier\">deploy.yml</font> se declenche sur succes "
        "de CI, ouvre une session SSH vers le VPS, execute "
        "<font face=\"Courier\">docker compose pull &amp;&amp; up -d</font>, "
        "attend la marque <i>healthy</i> du backend, et bascule "
        "automatiquement sur l’ancien tag en cas d’echec.",
        styles["Body"],
    ))
    story.append(Paragraph(
        "Le deploiement automatique <b>n’est pas encore actif</b> car "
        "les trois secrets GitHub "
        "(<font face=\"Courier\">VPS_HOST</font>, "
        "<font face=\"Courier\">VPS_USER</font>, "
        "<font face=\"Courier\">VPS_SSH_PRIVATE_KEY</font>) n’ont pas "
        "encore ete poses. Cette retention est volontaire afin de valider "
        "manuellement le premier deploiement.",
        styles["Body"],
    ))

    story.append(Paragraph("6.5  Sauvegardes", styles["H2"]))
    story.append(Paragraph(
        "Postgres beneficie d’un cron interne quotidien a 03h00 UTC "
        "qui execute <font face=\"Courier\">pg_dump</font> compresse vers "
        "le volume <font face=\"Courier\">gathe-finance-prod_backups</font>. "
        "La retention est fixee a 30 jours. <b>L’audit attire "
        "l’attention sur l’absence de replication hors-VPS</b> : "
        "si l’hote est compromis ou perdu, la DB et ses sauvegardes "
        "disparaissent ensemble. La mise en place d’un push "
        "<font face=\"Courier\">rsync</font> chiffre vers un stockage tiers "
        "(Backblaze B2, OVH PCA) est recommandee dans le mois.",
        styles["Body"],
    ))

    story.append(PageBreak())

    # =========== 07 FINDINGS ===========
    story.append(section_band("07. Findings classes par severite", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Legende des severites", styles["H2"]))
    leg = [
        ["Severite", "Definition", "Delai attendu"],
        ["CRITIQUE", "Blocage metier, securite ou perte de donnees imminente", "Sous 24 heures"],
        ["MAJEUR", "Friction UX significative, contournable mais visible", "Sous 7 jours"],
        ["MINEUR", "Anomalie ergonomique ou cosmetique non bloquante", "Sous 30 jours"],
        ["INFO", "Recommandation d’optimisation", "Planifie"],
    ]
    story.append(styled_table(
        leg, col_widths=[28 * mm, 100 * mm, 38 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Inventaire des findings", styles["H2"]))
    findings = [
        ["ID", "Severite", "Composant", "Constat synthetique"],
        ["F-01", "MAJEUR", "Admin",
         "HTTP 400 sur /api/v1/* via le rewrite Next.js (page blanche dashboard)"],
        ["F-02", "MAJEUR", "Admin",
         "Racine / reste en “Chargement…” sans redirection vers /login"],
        ["F-03", "MAJEUR", "Portail membre",
         "Routes non prefixees /login, /dashboard, /savings renvoient 404"],
        ["F-04", "MINEUR", "CMS Wagtail",
         "Racine cms.*/ redirige silencieusement vers la vitrine"],
        ["F-05", "MINEUR", "Mobile",
         "62 infos/warnings d’analyse statique (unawaited_futures, etc.)"],
        ["F-06", "INFO", "Backups",
         "Aucune replication hors-VPS — risque corruption / ransomware"],
        ["F-07", "INFO", "CI/CD",
         "Secrets GitHub VPS_* pas encore poses — CD auto inactif"],
        ["F-08", "INFO", "Tara MoMo",
         "URL de webhook pas encore declaree dans le dashboard Tara"],
        ["F-09", "INFO", "Brevo",
         "Domaine expediteur horus-lab.com a verifier dans Brevo"],
    ]
    story.append(styled_table(
        findings, col_widths=[15 * mm, 22 * mm, 32 * mm, 97 * mm],
        styles=styles, first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(info_box(
        "Aucun finding CRITIQUE",
        "A la date du present rapport, l’audit n’a identifie "
        "aucun blocage securitaire ni perte de donnees imminente. Les "
        "corrections sont exclusivement liees a l’experience "
        "utilisateur et a des actions d’exploitation a finaliser.",
        styles, GREEN_OK,
    ))

    story.append(PageBreak())

    # =========== 08 PLAN DE REMEDIATION ===========
    story.append(section_band("08. Plan de remediation recommande", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Court terme (sous 7 jours)", styles["H2"]))
    short = [
        ["F-01", "Diagnostiquer et corriger l’erreur HTTP 400 du rewrite admin"],
        ["", "Verifier la valeur runtime de DJANGO_ALLOWED_HOSTS et de "
              "CSRF_TRUSTED_ORIGINS dans le conteneur backend ; si admin.* "
              "ne s’y trouve pas, l’ajouter via .env.prod puis recreer "
              "le service."],
        ["F-02", "Implementer la garde d’authentification cote admin"],
        ["", "Ajouter un middleware Next.js qui redirige tout chemin "
              "/(authed)/* vers /login lorsque le cookie de session est "
              "absent ou invalide."],
        ["F-03", "Activer le fallback de locale sur le portail membre"],
        ["", "Configurer le middleware next-intl pour rediriger /<path> "
              "vers /<defaultLocale>/<path> ; les liens transactionnels "
              "retrouveront leur cible."],
    ]
    tbl_short = Table(short, colWidths=[18 * mm, 148 * mm], hAlign="LEFT")
    tbl_short.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (0, 0), (0, -1), 2, BLUE),
    ]))
    story.append(tbl_short)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Moyen terme (sous 30 jours)", styles["H2"]))
    mid = [
        ["F-04", "Page d’orientation sur cms.gathe-finance.horus-lab.com/"],
        ["", "Ajouter une regle de redirection ou un template Wagtail "
              "neutre menant explicitement vers /admin/."],
        ["F-05", "Sweep mobile : unawaited_futures, trailing_commas, imports"],
        ["", "Operer un nettoyage cible puis durcir le "
              "analysis_options.yaml afin de prevenir les regressions."],
        ["F-06", "Replication des backups Postgres hors VPS"],
        ["", "Script cron quotidien rsync chiffre vers un bucket "
              "Backblaze B2 ou un espace OVH PCA."],
        ["F-07", "Activation du CD auto GitHub"],
        ["", "Poser les trois secrets GitHub apres validation manuelle "
              "d’un premier deploiement automatique sur un commit "
              "factice."],
    ]
    tbl_mid = Table(mid, colWidths=[18 * mm, 148 * mm], hAlign="LEFT")
    tbl_mid.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (0, 0), (0, -1), 2, BLUE),
    ]))
    story.append(tbl_mid)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Exploitation immediate", styles["H2"]))
    ops_im = [
        ["F-08", "Declarer le webhook Tara dans le dashboard taramoney.com"],
        ["", "URL : https://api.gathe-finance.horus-lab.com/api/v1/payments/"
              "webhook/tara/  ·  Secret : TARA_WEBHOOK_SECRET du .env.prod."],
        ["F-09", "Verifier le sender Brevo"],
        ["", "Console Brevo › Senders, Domains &amp; dedicated IPs : "
              "verifier que horus-lab.com est marque Verified, sinon "
              "ajouter SPF, DKIM et DMARC chez le registrar."],
        ["—", "Publier l’AAB sur Google Play Console"],
        ["", "Upload manuel de app-release.aab "
              "(audit/release ou mobile/build/app/outputs/bundle/release/) "
              "puis examen Google attendu 48 a 72 heures."],
    ]
    tbl_ops = Table(ops_im, colWidths=[18 * mm, 148 * mm], hAlign="LEFT")
    tbl_ops.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (0, 0), (0, -1), 2, GREEN_OK),
    ]))
    story.append(tbl_ops)

    story.append(PageBreak())

    # =========== 09 ANNEXES ===========
    story.append(section_band("09. Annexes techniques", styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        "9.1  Inventaire des codes HTTP observes", styles["H2"]))
    annex = [
        ["URL", "Methode", "Code"],
        ["gathe-finance.horus-lab.com/", "GET", "200"],
        ["portail.gathe-finance.horus-lab.com/", "GET", "200"],
        ["portail.gathe-finance.horus-lab.com/fr", "GET", "200"],
        ["portail.gathe-finance.horus-lab.com/login", "GET", "404"],
        ["admin.gathe-finance.horus-lab.com/", "GET", "200"],
        ["admin.gathe-finance.horus-lab.com/dashboard", "GET", "200 (page blanche)"],
        ["admin.gathe-finance.horus-lab.com/login", "GET", "200"],
        ["admin.gathe-finance.horus-lab.com/api/v1/admin/dashboard/", "GET", "400"],
        ["api.gathe-finance.horus-lab.com/healthz/", "GET", "200"],
        ["api.gathe-finance.horus-lab.com/api/v1/savings/info/", "GET", "200"],
        ["api.gathe-finance.horus-lab.com/api/v1/auth/login/", "POST", "400 (FR)"],
        ["cms.gathe-finance.horus-lab.com/", "GET", "302 vers vitrine"],
        ["cms.gathe-finance.horus-lab.com/admin/", "GET", "200"],
        ["cms.gathe-finance.horus-lab.com/api/v2/pages/", "GET", "200"],
    ]
    story.append(styled_table(
        annex, col_widths=[110 * mm, 22 * mm, 34 * mm], styles=styles,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("9.2  Inventaire des conteneurs en production", styles["H2"]))
    cont = [
        ["Conteneur", "Image", "Etat"],
        ["gathe-finance-prod-db-1", "postgres:16-alpine", "Up (healthy)"],
        ["gathe-finance-prod-backend-1", "ghcr.io/…/backend:latest", "Up (healthy)"],
        ["gathe-finance-prod-qcluster-1", "ghcr.io/…/backend:latest", "Up"],
        ["gathe-finance-prod-site-1", "ghcr.io/…/site:latest", "Up"],
        ["gathe-finance-prod-portal-1", "ghcr.io/…/portal:latest", "Up"],
        ["gathe-finance-prod-admin-1", "ghcr.io/…/admin:latest", "Up"],
        ["gathe-finance-prod-backup-1", "postgres:16-alpine", "Up"],
        ["backend-nginx-1 (mutualise)", "nginx:alpine", "Up"],
    ]
    story.append(styled_table(
        cont, col_widths=[55 * mm, 60 * mm, 51 * mm], styles=styles,
        first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("9.3  Bordereau de livraison mobile", styles["H2"]))
    bord = [
        ["Element", "Valeur"],
        ["Fichier", "mobile/build/app/outputs/bundle/release/app-release.aab"],
        ["Taille", "53,7 Mo"],
        ["SHA-256",
         "b329b3e7ab7689ef96eb7bb27aa4c10b97eefb0cbdc8003596ea54edceb90514"],
        ["Keystore", "mobile/android/keystore/gathefinance-upload.jks"],
        ["API_BASE_URL grave", "https://api.gathe-finance.horus-lab.com"],
    ]
    story.append(styled_table(
        bord, col_widths=[40 * mm, 126 * mm], styles=styles, first_col_bold=True,
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("9.4  Documents de reference", styles["H2"]))
    refs = [
        ("audit/AUDIT_2026-06-20.md", "Audit securite et regles metier"),
        ("audit/TESTS_PLAN.md", "Plan de tests recette utilisateur"),
        ("audit/PLAY_STORE.md", "Checklist publication Google Play"),
        ("infra/DEPLOYMENT.md", "Guide de deploiement complet"),
        ("architecture/BUSINESS_RULES_2026.md", "Source de verite regles metier 2026"),
    ]
    for path, desc in refs:
        story.append(Paragraph(
            f"<font face=\"Courier\" color=\"{BLUE.hexval()}\">{path}</font>"
            f"&nbsp;&nbsp;&nbsp; {desc}",
            styles["BodyLeft"],
        ))

    story.append(Spacer(1, 12 * mm))

    # Signature
    story.append(info_box(
        "Signature",
        "Rapport etabli par le <b>Groupe Horus-lab</b> — Cellule Audit "
        "&amp; Recette, a Douala, le <b>23 juin 2026</b>. Le present document "
        "a valeur de constat a date. Les corrections recommandees en section "
        "08 feront l’objet d’un rapport complementaire "
        "<i>Plan de remediation</i> une fois les actions executees et "
        "re-controlees.",
        styles, NAVY,
    ))

    return story


def main() -> None:
    out = Path(__file__).parent / "AUDIT_DEPLOIEMENT_2026-06-23.pdf"
    doc = BaseDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="Audit de deploiement Gathe Finance",
        author="Groupe Horus-lab",
        subject="Rapport d'audit post-deploiement",
    )

    frame = Frame(
        MARGIN_L, MARGIN_B,
        PAGE_W - MARGIN_L - MARGIN_R,
        PAGE_H - MARGIN_T - MARGIN_B,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
        showBoundary=0,
    )
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=cover_page),
        PageTemplate(id="content", frames=[frame], onPage=header_footer),
    ])

    styles = make_styles()
    story = build_story(styles)
    doc.build(story)
    print(f"PDF genere : {out}  ({out.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
