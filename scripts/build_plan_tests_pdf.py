"""Genere docs/PLAN_TESTS_DASHBOARD.pdf avec filigrane Gathe Finance.

Lance : python scripts/build_plan_tests_pdf.py
Output : docs/PLAN_TESTS_DASHBOARD.pdf
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parent.parent
LOGO = ROOT / "docs" / "assets" / "logo.png"  # alpha pleine, on baisse l'opacite
LOGO_FALLBACK = ROOT / "livre_projet" / "assets" / "logo_watermark.png"
OUTPUT = ROOT / "docs" / "PLAN_TESTS_DASHBOARD.pdf"

# Palette Gathe
INK = colors.HexColor("#0F172A")
SUBTLE = colors.HexColor("#475569")
BLUE = colors.HexColor("#1E3A8A")
EMERALD = colors.HexColor("#047857")
AMBER = colors.HexColor("#92400E")
LINE = colors.HexColor("#CBD5E1")
PAPER_BG = colors.HexColor("#FBF7F1")


# ---------------------------------------------------------------------------
# Filigrane
# ---------------------------------------------------------------------------

def _watermark_image() -> Path | None:
    """Retourne le logo a utiliser comme filigrane (genere une version
    transparente si besoin)."""
    src = LOGO if LOGO.exists() else (LOGO_FALLBACK if LOGO_FALLBACK.exists() else None)
    if not src:
        return None
    out = Path("/tmp/gathe_watermark.png")
    if out.exists() and out.stat().st_mtime > src.stat().st_mtime:
        return out
    img = Image.open(src).convert("RGBA")
    # Aplatir tout vers le bleu Gathe (#1E3A8A) avec opacite tres basse
    # pour que le filigrane reste discret derriere le texte tout en etant
    # perceptible a 100%.
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0:
                pixels[x, y] = (30, 58, 138, int(a * 0.06))
    img.save(out, format="PNG")
    return out


def _draw_background(canv: canvas.Canvas, doc) -> None:
    """Dessine le filigrane Gathe + footer page."""
    canv.saveState()
    page_w, page_h = A4
    # Filigrane centre
    wm = _watermark_image()
    if wm and wm.exists():
        wm_size = 12 * cm
        canv.drawImage(
            str(wm),
            (page_w - wm_size) / 2,
            (page_h - wm_size) / 2,
            width=wm_size,
            height=wm_size,
            mask="auto",
            preserveAspectRatio=True,
        )
    # Footer
    canv.setFont("Helvetica", 8)
    canv.setFillColor(SUBTLE)
    canv.drawString(20 * mm, 12 * mm, "Gathe Finance . Plan de tests dashboard admin")
    canv.drawRightString(
        page_w - 20 * mm, 12 * mm, f"Page {doc.page}"
    )
    # Filet bleu
    canv.setStrokeColor(BLUE)
    canv.setLineWidth(0.4)
    canv.line(20 * mm, 16 * mm, page_w - 20 * mm, 16 * mm)
    canv.restoreState()


# ---------------------------------------------------------------------------
# Contenu
# ---------------------------------------------------------------------------

def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=22, textColor=BLUE, spaceBefore=0, spaceAfter=10, alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=14, textColor=BLUE, spaceBefore=16, spaceAfter=6, alignment=TA_LEFT,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=11.5, textColor=INK, spaceBefore=10, spaceAfter=4, alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10, leading=14, textColor=INK,
            spaceBefore=2, spaceAfter=2, alignment=TA_JUSTIFY,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.5, leading=11, textColor=SUBTLE, alignment=TA_LEFT,
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=INK,
            spaceBefore=4, spaceAfter=4, alignment=TA_JUSTIFY,
            leftIndent=8, rightIndent=8, borderPadding=6,
            borderColor=LINE, borderWidth=0.5,
            backColor=colors.HexColor("#FEF3C7"),
        ),
        "label": ParagraphStyle(
            "label", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=10, textColor=BLUE,
            spaceBefore=0, spaceAfter=0, alignment=TA_LEFT,
        ),
    }


def _section(title: str, styles: dict) -> list:
    return [Spacer(1, 6), Paragraph(title, styles["h2"])]


def _flow(num: str, name: str, duration: str, styles: dict,
          objectif: str, prereq: list, etapes: list, criteres: list) -> list:
    """Bloc unique pour un flow de test, soude ensemble pour eviter une
    coupure entre titre et contenu."""
    items = [
        Spacer(1, 8),
        Paragraph(
            f"<b>[{num}] {name}</b>  &nbsp; <font size=9 color='#475569'>"
            f"&middot; {duration}</font>",
            styles["h3"],
        ),
        Paragraph(f"<b>Objectif.</b> {objectif}", styles["body"]),
    ]
    if prereq:
        items.append(Paragraph("<b>Pre-requis</b>", styles["label"]))
        for pr in prereq:
            items.append(Paragraph(f". {pr}", styles["body"]))
    items.append(Paragraph("<b>Etapes</b>", styles["label"]))
    for i, e in enumerate(etapes, 1):
        items.append(Paragraph(f"{i}. {e}", styles["body"]))
    items.append(Paragraph("<b>Criteres de validation</b>", styles["label"]))
    for c in criteres:
        items.append(Paragraph(f"&#9744; &nbsp; {c}", styles["body"]))
    return [KeepTogether(items)]


def _table_kv(rows: list[tuple[str, str]], styles: dict) -> Table:
    data = [[Paragraph(f"<b>{k}</b>", styles["body"]),
             Paragraph(v, styles["body"])] for k, v in rows]
    t = Table(data, colWidths=[55 * mm, 110 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title="Plan de tests dashboard . Gathe Finance",
        author="Edwin Tchakounte",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_background)])

    s = _styles()
    story: list = []

    # --- Cover bloc ---
    story.append(Paragraph("Gathe Finance", s["small"]))
    story.append(Paragraph("Plan de tests . Dashboard admin", s["h1"]))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "Document de recette destine au compte admin valideur. Liste les "
        "parcours a executer avant la mise a disposition aux utilisateurs "
        "finaux. Chaque flow precise l'URL, les pre-requis, les etapes et "
        "les criteres de validation.",
        s["body"],
    ))
    story.append(Spacer(1, 6))
    story.append(_table_kv([
        ("Emetteur", "Edwin Tchakounte"),
        ("Date", "26 juin 2026"),
        ("Environnement", "Production . https://admin.gathe-finance.horus-lab.com"),
        ("Compte admin de test", "tchambaedwin@gmail.com (mot de passe envoye separement)"),
    ], s))

    # --- Bloc 1 : Critiques ---
    story.extend(_section("Bloc 1 . Flows critiques (impact financier direct)", s))
    story.extend(_flow(
        "1", "Adhesion bout-en-bout", "~ 30 minutes", s,
        objectif=(
            "Valider le parcours complet depuis la demande publique jusqu'a "
            "l'activation automatique du membre."
        ),
        prereq=[
            "Une demande en attente sur <b>/admin/membership-requests</b>.",
            "Photos d'identite, plan localisation et CNI recto/verso au format JPG/PNG.",
            "Ou soumettre une nouvelle demande via <i>gathe-finance.horus-lab.com/fr/devenir-membre</i>.",
        ],
        etapes=[
            "Ouvrir <b>/admin/membership-requests</b> puis cliquer <i>Detail</i> sur la demande. Verifier que les 4 documents s'affichent en preview inline.",
            "Cliquer <b>Entretien</b>, choisir Favorable, saisir un avis et enregistrer. L'email <i>Ton entretien d'admission</i> est expedie via Brevo (template <code>membership.interview_scheduled</code>). La chip <b>Entretien favorable</b> doit apparaitre sur la ligne.",
            "Cliquer <b>Approuver</b>. Le Member est cree en statut SUSPENDU, l'email <i>Bienvenue chez Gathe Finance</i> est envoye avec le PDF reglement en piece jointe.",
            "Cote portail ou mobile, le membre se connecte et regle les trois frais : adhesion (10 000), inscription (2 000), carnet (1 000) soit 13 000 XAF au total.",
            "Verifier sur <b>/admin/members?statut=actif</b> que le membre est passe en ACTIF des le troisieme paiement (hook CH-2). Email <i>Compte active</i> recu.",
        ],
        criteres=[
            "Les quatre documents s'affichent depuis la modale Detail.",
            "Email d'entretien recu avec l'issue favorable ou defavorable.",
            "Bouton Approuver desactive tant qu'aucun entretien n'a ete enregistre.",
            "Le Member apparait dans /admin/members?statut=suspendu apres approbation.",
            "Apres les trois frais payes, Member.statut bascule a ACTIF (hook CH-2).",
        ],
    ))
    story.extend(_flow(
        "2", "Credit voie 1 . BRC (depot a regulariser comptant)", "~ 45 minutes", s,
        objectif="Valider la double approbation CH-6 (provisoire, visite terrain, definitive) ainsi que le decaissement automatise par Tara.",
        prereq=[
            "Compte test <code>paul.test@test.local</code> avec mot de passe <code>test1234</code>, demande en EN_ATTENTE.",
            "Ou utiliser un nouveau membre qui depose une demande de credit depuis le mobile.",
        ],
        etapes=[
            "Ouvrir <b>/admin/loan-requests?statut=en_instruction</b> puis la demande concernee.",
            "Cliquer <b>Decision provisoire</b> puis <i>Approuver provisoirement</i>. Le statut passe a APPROUVEE_PROVISOIRE.",
            "Cliquer <b>Visite terrain effectuee</b> et saisir le rapport. Les champs <code>field_visit_done_at</code> et <code>field_visit_by</code> sont renseignes.",
            "Cliquer <b>Decision definitive</b> et approuver. Un Loan et son echeancier (1 a 24 lignes selon duree) sont crees, l'email <i>Credit decaisse</i> est envoye.",
            "Sur <b>/admin/loans/{id}</b> cliquer <b>Decaisser via Tara</b>. Verifier le payout MOMO/OM dans les logs et la retenue de 10 % d'interets a la source (CH-11).",
            "Enregistrer un remboursement depuis <b>/admin/payments</b> et verifier l'imputation FIFO sur les echeances.",
        ],
        criteres=[
            "Sequence des trois statuts respectee (provisoire, visite, definitive).",
            "Echeancier coherent avec terms.py (paliers 10 % par transaction).",
            "Email envoye a chaque etape decisionnelle.",
            "Audit log trace toutes les decisions avec acteur et IP.",
            "Le cron retards (V2) bascule en EN_RETARD apres date d'echeance.",
        ],
    ))
    story.extend(_flow(
        "3", "Credit voie 2 . Avaliste", "~ 20 minutes", s,
        objectif="Valider le flow LOT 10 (consentement de l'avaliste sous 24 heures).",
        prereq=["Deux comptes membres actifs avec solde suffisant cote avaliste."],
        etapes=[
            "Le membre A depose une demande en designant le membre B comme avaliste. Statut EN_ATTENTE_AVALISTE.",
            "Le membre B recoit l'email <i>Designation comme avaliste</i> ainsi qu'une notification in-app (NotifKind.avaliste).",
            "Le membre B ouvre l'app, va dans <b>Mes mandats avaliste</b> et choisit Accepter ou Refuser.",
            "Si l'avaliste accepte, la demande bascule en EN_INSTRUCTION. S'il refuse, statut REJETEE_AVALISTE (terminal).",
            "Confirmer que /admin/loan-requests filtre EN_ATTENTE_AVALISTE est vide apres reponse.",
        ],
        criteres=[
            "Email et notification in-app expedies a l'avaliste designe.",
            "La regle Avaliste cap solde est respectee (un avaliste ne garantit pas plus que son propre solde cumule).",
            "Apres un refus, le membre A peut redesigner un autre avaliste.",
        ],
    ))
    story.extend(_flow(
        "4", "Credit voie 3 . Campagne micro-credit", "~ 25 minutes", s,
        objectif="Valider le cycle complet d'une campagne (LOT 11 et LOT 16).",
        prereq=["Compte admin avec acces /admin/campaigns."],
        etapes=[
            "Sur <b>/admin/campaigns</b> creer une campagne <i>Test 2026-06</i>, profil cible AGRICULTEUR, dates aujourd'hui a +30 jours, montants 50 000 a 200 000 XAF, flyer JPG.",
            "Verifier diffusion : email <i>Nouvelle campagne micro-credit</i> envoye a tous les membres ACTIF (template <code>campaign.created</code>), notification in-app, visibilite cote mobile sur Credit voie 3.",
            "Faire postuler un membre. Statut EN_VALIDATION_CAMPAGNE.",
            "L'admin valide l'activite. La demande bascule en EN_INSTRUCTION.",
            "Verifier le cron close_expired_campaigns qui ferme automatiquement a date_fin.",
        ],
        criteres=[
            "Notification email et in-app diffusees a tous les ACTIF.",
            "Flyer accessible publiquement (/media/coop/campaigns/).",
            "Export CSV des beneficiaires fonctionne.",
            "Le soft-delete cache la campagne sans la supprimer du systeme.",
        ],
    ))

    # --- Bloc 2 : Operationnel ---
    story.append(PageBreak())
    story.extend(_section("Bloc 2 . Flows operationnels quotidiens", s))
    story.extend(_flow(
        "5", "Cotisations journalieres", "~ 15 minutes", s,
        objectif="Verifier la collecte journaliere et la commission 1 % fin de mois.",
        prereq=["Au moins un membre actif qui cotise depuis plusieurs jours."],
        etapes=[
            "Ouvrir <b>/admin/payments?type=cotisation</b>, controler la liste.",
            "Le cron <code>apply_monthly_commission</code> retient 1 % en fin de mois sur les cotisations.",
            "Tester le multi-jours pre-paye (LOT 6) : un paiement pour N jours doit creer N entrees Cotisation.",
        ],
        criteres=[
            "Commission 1 % appliquee (jamais 0).",
            "Tunable via AppSetting si besoin de derogation.",
        ],
    ))
    story.extend(_flow(
        "6", "Retraits epargne", "~ 15 minutes", s,
        objectif="Valider le debit atomique et le payout multi-canal (Tara ou presentiel).",
        prereq=["Un WithdrawalRequest en attente."],
        etapes=[
            "Sur <b>/admin/withdrawals</b> ouvrir une demande.",
            "Approuver et choisir le canal : Tara MOMO/OM (payout automatique) ou Presentiel (Remis en main propre).",
            "Verifier le debit atomique du solde epargne dans la base.",
        ],
        criteres=[
            "Solde debite a l'instant T (transaction atomique).",
            "Email <i>Retrait approuve</i> envoye.",
            "Audit log mis a jour.",
        ],
    ))
    story.extend(_flow(
        "7", "Commandes de carnets", "~ 10 minutes", s,
        objectif="Verifier le pilotage des carnets et l'activation post-paiement.",
        prereq=["Un membre qui vient de payer son frais_carnet."],
        etapes=[
            "Ouvrir <b>/admin/booklet-orders</b>.",
            "Une fois le paiement enregistre, marquer la commande Imprime puis Livre.",
            "Le hook CH-2 active automatiquement le membre si tous les frais sont payes.",
        ],
        criteres=[
            "Le statut bascule a chaque transition.",
            "Membre ACTIF si les trois frais sont valides.",
        ],
    ))
    story.extend(_flow(
        "8", "Contentieux . mise en demeure", "~ 15 minutes", s,
        objectif="Verifier l'enregistrement de la mise en demeure (Article 13) et l'escalade R1.",
        prereq=["Au moins un Loan en EN_RETARD."],
        etapes=[
            "Sur <b>/admin/loans?statut=en_retard</b> ouvrir un dossier.",
            "Cliquer <b>Enregistrer mise en demeure</b>, uploader le PDF et la date d'envoi recommande.",
            "Sur <b>/admin/escalations</b> verifier les 4 phases : Phase D (saisie epargne) puis Phase E (poursuites).",
        ],
        criteres=[
            "Email Mise en demeure envoye (valeur juridique).",
            "Cron R1 saisit l'epargne automatiquement apres le delai de grace.",
            "Bascule Phase E si l'epargne ne couvre pas le solde.",
        ],
    ))

    # --- Bloc 3 : Communication ---
    story.extend(_section("Bloc 3 . Communication et contenu", s))
    story.extend(_flow(
        "9", "Annonces broadcast", "~ 10 minutes", s,
        objectif="Diffuser un message a tous les ACTIF avec retour visible mobile/portail.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/announcements</b> creer une annonce avec titre, corps et bientot image jointe.",
            "Publier. La diffusion arrive en push mobile (NotifKind.announcement), dans /notifications cote mobile et dans /portail/notifications.",
        ],
        criteres=[
            "L'annonce s'affiche dans toutes les destinations.",
            "Le compteur d'annonces non lues s'incremente.",
        ],
    ))
    story.extend(_flow(
        "10", "Blog et articles", "~ 10 minutes", s,
        objectif="Editer un article Wagtail et controler la vitrine publique.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/blog</b> editer un article.",
            "Publier puis ouvrir <i>gathe-finance.horus-lab.com/fr/blog/{slug}</i>.",
            "Depublier ensuite et confirmer le 404 ou la redirection.",
        ],
        criteres=[
            "Image de couverture affichee.",
            "Texte lisible avec marges agreables et style percutant.",
        ],
    ))

    # --- Bloc 4 : Administration ---
    story.append(PageBreak())
    story.extend(_section("Bloc 4 . Administration et parametrage", s))
    story.extend(_flow(
        "11", "AppSettings . refonte tunable", "~ 15 minutes", s,
        objectif="Modifier un parametre business et verifier la propagation.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/settings</b> modifier par exemple <code>frais_adhesion</code> a 12 000.",
            "Tester cote portail ou mobile que la nouvelle valeur s'applique au paiement.",
            "Modifier un parametre marque sensitive. Une modale de confirmation doit s'afficher.",
        ],
        criteres=[
            "La nouvelle valeur est appliquee a chaud sans redeploiement.",
            "Audit log mentionne le changement.",
        ],
    ))
    story.extend(_flow(
        "12", "Crons admin", "~ 10 minutes", s,
        objectif="Verifier l'execution manuelle des taches periodiques.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/crons</b> ouvrir un cron (ex. interets epargne).",
            "Cliquer <b>Run now</b>, confirmer l'execution et le log.",
            "Modifier la cron expression et verifier la prochaine planification.",
        ],
        criteres=["L'execution manuelle aboutit sans erreur.", "Les logs sont consultables."],
    ))
    story.extend(_flow(
        "13", "FormSchema editor (CH-4 et CH-5)", "~ 15 minutes", s,
        objectif="Modifier le formulaire de credit ou d'adhesion et constater la propagation mobile/portail.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/form-schemas</b> editer le formulaire credit.",
            "Ajouter un champ libre Activite secondaire et publier.",
            "Verifier que le mobile et le portail recoivent le nouveau schema.",
        ],
        criteres=["Le nouveau champ apparait cote mobile sans rebuild.", "Validation cote serveur OK."],
    ))
    story.extend(_flow(
        "14", "Exports CSV et PDF", "~ 10 minutes", s,
        objectif="Verifier les exports operationnels.",
        prereq=[],
        etapes=[
            "Sur /admin/members, /admin/loans, /admin/payments et /admin/escalations utiliser le menu Export.",
            "Ouvrir les fichiers CSV (UTF-8 + BOM) et verifier les colonnes attendues.",
        ],
        criteres=["Les fichiers s'ouvrent proprement.", "Les valeurs financieres sont coherentes."],
    ))
    story.extend(_flow(
        "15", "Audit log", "~ 10 minutes", s,
        objectif="Verifier la tracabilite des actions critiques.",
        prereq=[],
        etapes=[
            "Sur <b>/admin/audit</b> filtrer par action (approuver, decaisser, supprimer).",
            "Chaque entree montre acteur, IP, horodatage et details.",
            "Pour la suite : sauvegarde TXT toutes les 72 heures (cron a venir).",
        ],
        criteres=["Toutes les actions sensibles sont presentes.", "Aucune entree manquante."],
    ))

    # --- Bloc 5 : Securite ---
    story.extend(_section("Bloc 5 . Securite et acces", s))
    story.extend(_flow(
        "16", "Permissions", "~ 10 minutes", s,
        objectif="Empecher l'acces admin a un compte non staff.",
        prereq=[],
        etapes=[
            "Se deconnecter du compte admin.",
            "Se connecter avec un compte membre (paul.test@test.local).",
            "Tenter d'acceder a /admin/*. Le routeur doit rediriger.",
            "Tester un appel curl direct a l'API admin. Reponse attendue : 403.",
        ],
        criteres=["Aucun acces a l'admin pour un compte non staff."],
    ))
    story.extend(_flow(
        "17", "Media protege", "~ 5 minutes", s,
        objectif="Cloisonner les pieces sensibles tout en gardant les documents officiels publics.",
        prereq=[],
        etapes=[
            "Curl sans cookie sur /media/coop/adhesion/cni/... Doit retourner 403.",
            "Curl sans cookie sur /media/coop/assets/... (reglement). Doit retourner 200.",
        ],
        criteres=["Les CNI restent privees, le reglement reste public."],
    ))
    story.extend(_flow(
        "18", "CSRF", "~ 5 minutes", s,
        objectif="Refuser un POST admin sans token CSRF.",
        prereq=[],
        etapes=["POST sur /api/v1/admin/* sans token. Reponse attendue : 403."],
        criteres=["Toutes les mutations admin sont protegees."],
    ))

    # --- Ordre conseille + comptes test ---
    story.append(PageBreak())
    story.extend(_section("Ordre de passage recommande", s))
    story.append(Paragraph(
        "Jour 1 . environ trois heures : Bloc 1 (flows critiques, deux heures) "
        "puis Bloc 2 (flows operationnels, une heure).",
        s["body"],
    ))
    story.append(Paragraph(
        "Jour 2 . environ une heure et demie : Bloc 3 (communication, vingt "
        "minutes), Bloc 4 (administration, cinquante minutes) puis Bloc 5 "
        "(securite, vingt minutes).",
        s["body"],
    ))

    story.extend(_section("Comptes de test sur production", s))
    story.append(Paragraph(
        "<b>Compte admin valideur :</b> tchambaedwin@gmail.com (mot de passe "
        "envoye separement par Edwin).",
        s["body"],
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Membres de test (mot de passe : <code>test1234</code>)", s["label"]))
    story.append(_table_kv([
        ("jean.kamga@test.local", "Demande campagne (en_validation_campagne)."),
        ("paul.test@test.local", "Demande de credit en_attente."),
        ("sylvie.test@test.local", "Demande de credit en_instruction."),
        ("alain.test@test.local", "Demande de credit approuvee_provisoire."),
        ("rachel.test@test.local", "Demande de credit rejetee."),
        ("nadine.fotso@test.local", "Credit ACTIF decaisse."),
        ("eric.muna@test.local", "Credit ACTIF avec une echeance payee."),
        ("claire.ndongo@test.local", "Credit en RETARD."),
        ("david.nyamsi@test.local", "Credit CLOTURE (historique)."),
    ], s))

    story.extend(_section("Signalement de bug", s))
    story.append(Paragraph(
        "Reporter par email a edwin@horus-lab.com et tchambaedwin@gmail.com en "
        "indiquant l'URL exacte, une capture d'ecran, le compte utilise, les "
        "etapes pour reproduire le probleme, ainsi que le comportement attendu "
        "et le comportement observe.",
        s["body"],
    ))

    doc.build(story)
    print(f"OK -> {OUTPUT.relative_to(ROOT)}")
    print(f"Taille : {os.path.getsize(OUTPUT) // 1024} KB")


if __name__ == "__main__":
    build()
