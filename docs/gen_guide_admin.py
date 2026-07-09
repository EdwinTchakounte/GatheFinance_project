# -*- coding: utf-8 -*-
"""Génère le Guide d'administration (planificateurs + paramètres) en PDF.

Texte client-friendly, justifié, sans jargon interne. Rédacteur : TCHAMBA
TCHAKOUNTE Edwin.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    NextPageTemplate, PageBreak, KeepTogether,
)

NAVY = colors.HexColor("#0E4D92")
GREEN = colors.HexColor("#3AAA35")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E2E8F0")
CREAM = colors.HexColor("#F7F5F0")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                    fontSize=16, textColor=NAVY, spaceBefore=6, spaceAfter=10, leading=20)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                    fontSize=11.5, textColor=NAVY, spaceBefore=14, spaceAfter=4, leading=15)
ITEM = ParagraphStyle("ITEM", fontName="Helvetica-Bold", fontSize=10.3, textColor=INK,
                      spaceBefore=8, spaceAfter=1, leading=13)
META = ParagraphStyle("META", fontName="Helvetica-Oblique", fontSize=8.6, textColor=GREEN,
                      spaceAfter=2, leading=11)
BODY = ParagraphStyle("BODY", fontName="Helvetica", fontSize=9.6, textColor=INK,
                      alignment=TA_JUSTIFY, leading=13.5, spaceAfter=2)
INTRO = ParagraphStyle("INTRO", parent=BODY, fontSize=10, textColor=colors.HexColor("#374151"),
                       spaceAfter=8)
COVER_T = ParagraphStyle("CT", fontName="Helvetica-Bold", fontSize=26, textColor=NAVY,
                         alignment=TA_CENTER, leading=32)
COVER_S = ParagraphStyle("CS", fontName="Helvetica", fontSize=13, textColor=INK,
                         alignment=TA_CENTER, leading=18)
COVER_M = ParagraphStyle("CM", fontName="Helvetica", fontSize=10.5, textColor=MUTED,
                         alignment=TA_CENTER, leading=16)


def on_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    # bandeau haut
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.6)
    canvas.line(20*mm, h-16*mm, w-20*mm, h-16*mm)
    canvas.setFont("Helvetica", 7.5); canvas.setFillColor(MUTED)
    canvas.drawString(20*mm, h-14*mm, "GATHE Finance — Guide d'administration")
    canvas.drawRightString(w-20*mm, h-14*mm, "Espace d'administration")
    # pied
    canvas.line(20*mm, 15*mm, w-20*mm, 15*mm)
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 7.5)
    canvas.drawString(20*mm, 11*mm, "Rédacteur : TCHAMBA TCHAKOUNTE Edwin")
    canvas.drawRightString(w-20*mm, 11*mm, "Page %d" % doc.page)
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, h-6*mm, w, 6*mm, fill=1, stroke=0)
    canvas.setFillColor(GREEN)
    canvas.rect(0, h-8*mm, w, 2*mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED); canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(w/2, 15*mm, "Document interne — GATHE Finance")
    canvas.restoreState()


def card(flowables):
    """Encadre une liste de flowables dans une carte crème à liseré."""
    t = Table([[flowables]], colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, GREEN),
    ]))
    return t


# ---------------------------------------------------------------------------
# CONTENU — Planificateurs automatiques (cron)
# ---------------------------------------------------------------------------
CRONS = [
    ("Clôture mensuelle des cotisations", "Chaque mois, le 1er à 02h00",
     "À la fin de chaque mois, ce traitement clôture les comptes de collecte journalière. "
     "Il retient la commission de gestion (1 % par défaut, réglable) sur le solde accumulé, "
     "puis, selon le choix enregistré pour le compte, restitue le montant au membre ou le "
     "bascule automatiquement vers son épargne classique. C'est l'opération qui matérialise "
     "la contrepartie de la coopérative sur la collecte."),

    ("Suivi des échéances d'épargne classique", "Chaque jour à 03h30",
     "Ce traitement surveille la date anniversaire (douze mois) de chaque compte d'épargne "
     "classique. À l'approche de l'échéance il envoie les rappels au membre ; à maturité il "
     "prépare la restitution intégrale et le paiement des frais de ré-inscription ; et si le "
     "membre ne renouvelle pas dans le délai de grâce, il archive le compte. Il garantit que "
     "le cycle annuel de l'épargne se déroule sans intervention manuelle."),

    ("Détection des retards de crédit", "Chaque jour à 03h00",
     "Il parcourt l'ensemble des échéances de crédit et repère celles dont la date est "
     "dépassée. Le crédit concerné est marqué « en retard » et les relances graduées prévues "
     "par le règlement sont déclenchées. C'est le point de départ du suivi du recouvrement."),

    ("Rappel des échéances à venir", "Chaque jour à 08h00",
     "Quelques jours avant la date d'une échéance, il prévient le membre afin de favoriser un "
     "paiement à temps et de limiter les retards. Il s'agit d'une action préventive, distincte "
     "de la détection des retards déjà survenus."),

    ("Vérification des paiements Mobile Money", "Toutes les 15 minutes",
     "Ce traitement est le filet de sécurité des paiements Mobile Money. Lorsqu'un versement "
     "reste « en attente » (par exemple si la confirmation instantanée du prestataire n'est "
     "pas parvenue), il interroge directement le prestataire pour obtenir le statut réel et "
     "confirmer ou rejeter l'opération. Il assure qu'aucun paiement validé ne reste bloqué."),

    ("Alerte des paiements bloqués", "Chaque heure",
     "Si des paiements demeurent en attente au-delà d'une heure — signe d'une panne du "
     "prestataire ou d'un service arrêté — il envoie un courriel d'alerte aux administrateurs. "
     "C'est un outil de supervision qui permet de réagir rapidement à un incident."),

    ("Rappel de ré-inscription annuelle", "Chaque jour à 09h00",
     "Il alerte en douceur les membres à l'approche de la date anniversaire de leur adhésion, "
     "afin qu'ils procèdent à leur ré-inscription et conservent un compte actif."),

    ("Clôture des fenêtres de financement", "Toutes les 15 minutes",
     "Pour les crédits financés par l'épargne des membres prêteurs, chaque prêteur sollicité "
     "dispose d'un délai pour accepter. Passé ce délai, ce traitement applique automatiquement "
     "l'acceptation, puis finalise le financement du crédit ou réaffecte les montants "
     "manquants. Il évite qu'un dossier reste en attente d'une réponse indéfiniment."),

    ("Clôture des micro-campagnes échues", "Chaque jour à 04h15",
     "Il ferme automatiquement les campagnes de micro-crédit dont la date de fin est passée, "
     "de sorte qu'aucune nouvelle candidature ne puisse être déposée sur une campagne "
     "terminée."),

    ("Escalade judiciaire automatique", "Chaque jour à 05h00",
     "Lorsque le mode automatique est activé, il ouvre un dossier de recouvrement judiciaire "
     "pour les crédits en contentieux dont le délai réglementaire est dépassé. En mode manuel "
     "il reste sans effet : c'est alors l'administrateur qui décide d'engager la procédure."),

    ("Archivage du journal d'audit", "Tous les 3 jours à 02h30",
     "Il compresse et archive dans un fichier les entrées du journal d'audit de plus de trois "
     "jours, puis les retire de la base pour l'alléger. Aucune information n'est perdue : "
     "l'historique reste consultable dans les archives."),

    ("Intérêts d'épargne (dispositif hérité)", "Désactivé par défaut",
     "Ce traitement, hérité de l'organisation précédente, créditait des intérêts mensuels sur "
     "la collecte. Il est conservé mais désactivé par défaut dans le fonctionnement actuel ; "
     "il ne s'exécute que si l'on réactive explicitement le paramètre correspondant."),
]


# ---------------------------------------------------------------------------
# CONTENU — Paramètres de configuration (regroupés)
# ---------------------------------------------------------------------------
PARAMS = [
 ("Membre & ancienneté", [
   ("Format du numéro de membre", "GF-{year}-{seq:04d}",
    "Modèle utilisé pour générer automatiquement le numéro d'identification de chaque "
    "membre. Les repères {year} et {seq} sont remplacés par l'année et un numéro d'ordre."),
   ("Ancienneté minimum (mois)", "12",
    "Nombre de mois d'ancienneté à partir duquel un membre est considéré comme « Ancien ». "
    "Ce statut ouvre l'accès à la voie de crédit réservée aux membres établis et permet de "
    "se porter garant d'un autre membre."),
 ]),
 ("Collecte journalière", [
   ("Montant minimum journalier (FCFA)", "1 000",
    "Plancher d'un versement de collecte pour une journée. Le membre peut verser davantage ; "
    "un pré-paiement de plusieurs jours doit être un multiple de ce montant."),
   ("Pré-paiement maximum (jours)", "30",
    "Nombre maximal de jours qu'un membre peut régler d'avance en un seul versement de "
    "collecte."),
   ("Action de fin de mois (par défaut)", "Retrait (cash)",
    "Comportement appliqué par défaut à la clôture mensuelle : restituer le solde au membre "
    "en espèces, ou le basculer vers l'épargne classique."),
   ("Clôture mensuelle activée", "Activée",
    "Interrupteur général de la clôture mensuelle automatique des comptes de collecte."),
   ("Commission de fin de mois (taux)", "0,01 (soit 1 %)",
    "Part prélevée par la coopérative sur le solde d'un compte de collecte à la clôture "
    "mensuelle. La valeur 0 correspond à une restitution intégrale, 0,02 à 2 %, etc."),
 ]),
 ("Épargne classique", [
   ("Durée du contrat (mois)", "12",
    "Durée d'un cycle d'épargne classique au terme duquel le solde est restitué et le contrat "
    "peut être renouvelé."),
   ("Frais de ré-inscription (FCFA)", "5 000",
    "Montant demandé à l'échéance des douze mois pour renouveler le contrat d'épargne "
    "classique."),
   ("Délai de grâce de ré-inscription (jours)", "30",
    "Délai accordé après l'échéance pour régler les frais de renouvellement avant que le "
    "compte ne soit archivé."),
   ("Heure limite de dépôt (Douala)", "17 h",
    "Un dépôt effectué après cette heure est comptabilisé au jour ouvré suivant."),
   ("Lieu de collecte (libellé)", "GATHE Finance — Akwa, Douala (Bercy)",
    "Adresse affichée au membre lorsqu'il choisit de se présenter à l'agence pour verser."),
 ]),
 ("Réinscription des membres", [
   ("Préavis de réinscription (jours)", "30",
    "Nombre de jours avant la date anniversaire d'adhésion à partir duquel le membre reçoit "
    "un rappel l'invitant à se réinscrire."),
 ]),
 ("Crédit (règles générales)", [
   ("Seuil de passage en contentieux (jours)", "90",
    "Au-delà de ce nombre de jours de retard, l'échéance de crédit bascule en contentieux."),
   ("Préavis d'échéance (jours)", "3",
    "Nombre de jours avant une échéance auquel le rappel préventif est envoyé au membre."),
   ("Prorogation de reconduction (mois)", "1",
    "Durée supplémentaire fixe accordée lorsqu'un crédit est reconduit."),
   ("Grâce avant contentieux après pénalité (jours)", "30",
    "Délai entre l'application de la pénalité et le passage en contentieux du crédit."),
   ("Pénalité par échéance", "Désactivée",
    "Lorsqu'elle est activée, une pénalité s'applique à chaque échéance manquée. Par défaut, "
    "seule la pénalité globale est appliquée."),
 ]),
 ("Épargne-prêteur", [
   ("Tranche prêteur minimale (FCFA)", "5 000",
    "Montant minimal qu'un membre peut engager en une tranche destinée à financer les "
    "crédits, afin d'éviter les très petits montants."),
   ("Ancienneté minimale du prêteur (mois)", "0",
    "Ancienneté requise pour qu'un membre puisse mettre son épargne à disposition du "
    "financement des crédits. La valeur 0 signifie aucune condition d'ancienneté."),
   ("Partage des intérêts du crédit (taux)", "0,5 (soit 50 %)",
    "Fraction des intérêts d'un crédit reversée aux membres qui l'ont financé (0,5 = partage "
    "à parts égales avec la coopérative)."),
 ]),
 ("Financement des crédits", [
   ("Fenêtre d'acceptation (heures)", "24",
    "Délai laissé à un prêteur sollicité pour accepter de financer un crédit. Passé ce délai, "
    "l'acceptation est appliquée automatiquement."),
   ("Stratégie d'allocation", "Gros prêteurs d'abord",
    "Méthode de sélection des prêteurs pour financer un crédit : privilégier les tranches les "
    "plus importantes, ou répartir équitablement entre les prêteurs."),
 ]),
 ("Éligibilité au crédit", [
   ("Voie « Ancien » activée", "Activée",
    "Interrupteur de la voie de crédit réservée aux membres anciens et reconnus. Désactivée, "
    "elle bloque les demandes directes par cette voie."),
   ("Voie « Avaliste » activée", "Activée",
    "Interrupteur de la voie de crédit avec garant (avaliste)."),
   ("Voie « Micro-campagne » activée", "Activée",
    "Interrupteur de la voie de crédit adossée à une campagne de micro-crédit."),
   ("Justificatif obligatoire pour la voie « Ancien »", "Oui",
    "Lorsque cette exigence est levée, l'ancienneté seule suffit pour la voie réservée aux "
    "membres établis."),
   ("Ordre de priorité des voies", "Ancien, Avaliste, Campagne",
    "Ordre dans lequel les voies de crédit sont examinées : la première qui correspond à la "
    "situation du membre s'applique. Une voie retirée de la liste est désactivée."),
 ]),
 ("Garantie par avaliste", [
   ("Couverture minimale de l'avaliste (taux)", "1,00 (soit 100 %)",
    "Rapport minimal exigé entre l'épargne cumulée du demandeur et de son garant, d'une part, "
    "et le montant demandé, d'autre part."),
   ("Plusieurs avalistes autorisés", "Non",
    "Détermine si un même crédit peut être garanti par plusieurs avalistes."),
 ]),
 ("Micro-campagnes de crédit", [
   ("Plancher de montant (FCFA)", "5 000",
    "Montant minimal pré-rempli à la création d'une campagne de micro-crédit."),
   ("Plafond de montant (FCFA)", "50 000",
    "Montant maximal pré-rempli à la création d'une campagne de micro-crédit."),
   ("Taux de la campagne", "0,10 (soit 10 %)",
    "Taux d'intérêt pré-rempli pour une campagne de micro-crédit."),
   ("Durée de recouvrement (jours)", "60",
    "Durée par défaut du recouvrement d'un crédit de campagne, réglé par collectes "
    "journalières."),
 ]),
 ("Recouvrement sur l'épargne", [
   ("Ordre des sources de saisie", "Demandeur puis avaliste",
    "Ordre dans lequel l'épargne est mobilisée pour recouvrer un crédit impayé : d'abord "
    "l'épargne du demandeur, puis, si nécessaire, celle du garant."),
   ("Inclure l'avaliste au recouvrement", "Oui",
    "Détermine si l'épargne du garant peut être mobilisée pour couvrir un crédit impayé."),
   ("Protéger l'épargne déjà engagée", "Oui",
    "Empêche la saisie de l'épargne déjà engagée dans le financement d'un autre crédit. À ne "
    "pas désactiver hors d'un contrôle exceptionnel."),
 ]),
 ("Escalade judiciaire", [
   ("Mode d'escalade", "Manuel",
    "Détermine la manière dont un dossier passe en recouvrement judiciaire : à la main de "
    "l'administrateur, automatiquement, ou après un préavis pendant lequel il peut intervenir."),
   ("Délai de déclenchement automatique (jours)", "60",
    "Nombre de jours après l'échec du recouvrement amiable au terme desquels l'escalade "
    "judiciaire s'engage, en modes automatique et mixte."),
   ("Préavis à l'administrateur (jours)", "7",
    "En mode mixte, nombre de jours de préavis pendant lesquels l'administrateur peut "
    "intervenir avant le déclenchement automatique."),
 ]),
]


# ---------------------------------------------------------------------------
# Assemblage du document
# ---------------------------------------------------------------------------
def build(path):
    doc = BaseDocTemplate(path, pagesize=A4,
                          leftMargin=20*mm, rightMargin=20*mm,
                          topMargin=22*mm, bottomMargin=20*mm,
                          title="Guide d'administration — Planificateurs et Paramètres",
                          author="TCHAMBA TCHAKOUNTE Edwin")
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[frame], onPage=on_cover),
        PageTemplate(id="body", frames=[frame], onPage=on_page),
    ])

    S = []
    # ---- Couverture
    S.append(Spacer(1, 55*mm))
    S.append(Paragraph("Guide d'administration", COVER_T))
    S.append(Spacer(1, 4*mm))
    S.append(Paragraph("Planificateurs automatiques &amp; Paramètres de configuration", COVER_S))
    S.append(Spacer(1, 3*mm))
    S.append(Paragraph("Espace d'administration — GATHE Finance", COVER_M))
    S.append(Spacer(1, 40*mm))
    S.append(Paragraph("Rédacteur", COVER_M))
    S.append(Paragraph("<b>TCHAMBA TCHAKOUNTE Edwin</b>", COVER_S))
    S.append(NextPageTemplate("body"))
    S.append(PageBreak())

    # ---- Introduction
    S.append(Paragraph("Objet du document", H1))
    S.append(Paragraph(
        "Ce document décrit, en langage clair, deux ensembles d'outils disponibles dans "
        "l'espace d'administration de GATHE Finance : d'une part les <b>planificateurs "
        "automatiques</b>, qui exécutent seuls, à intervalles réguliers, les tâches "
        "récurrentes de la coopérative ; d'autre part les <b>paramètres de configuration</b>, "
        "qui permettent d'ajuster les règles de fonctionnement sans intervention technique. "
        "Chaque élément est présenté avec son rôle et, le cas échéant, sa valeur par défaut, "
        "afin que l'équipe d'administration comprenne précisément ce qu'elle pilote.", INTRO))

    # ---- Section 1 : planificateurs
    S.append(Paragraph("1. Les planificateurs automatiques", H1))
    S.append(Paragraph(
        "Un planificateur est une tâche que le système exécute automatiquement selon un "
        "rythme défini (chaque heure, chaque jour, chaque mois…), sans qu'un administrateur "
        "ait à la lancer. L'espace d'administration permet de consulter ces tâches, d'ajuster "
        "leur fréquence et, au besoin, de les exécuter immédiatement. Voici le rôle de "
        "chacune.", INTRO))
    for title, cadence, role in CRONS:
        block = [Paragraph(title, ITEM),
                 Paragraph("Fréquence : " + cadence, META),
                 Paragraph(role, BODY)]
        S.append(KeepTogether(card(block)))
        S.append(Spacer(1, 5))

    S.append(PageBreak())

    # ---- Section 2 : paramètres
    S.append(Paragraph("2. Les paramètres de configuration", H1))
    S.append(Paragraph(
        "Les paramètres permettent d'adapter les règles de la coopérative (montants, délais, "
        "taux, options activées ou non) directement depuis l'espace d'administration. Toute "
        "modification est prise en compte sans redéploiement technique. Ils sont regroupés "
        "ci-dessous par domaine ; la valeur par défaut indiquée est celle appliquée en "
        "l'absence de changement.", INTRO))
    for group, items in PARAMS:
        rows = [Paragraph(group, H2)]
        for label, default, role in items:
            rows.append(Paragraph(label + "  —  <font color='#3AAA35'>valeur par défaut : "
                                  + default + "</font>", ITEM))
            rows.append(Paragraph(role, BODY))
        S.append(KeepTogether(rows))

    doc.build(S)


if __name__ == "__main__":
    import sys
    build(sys.argv[1])
    print("OK", sys.argv[1])
