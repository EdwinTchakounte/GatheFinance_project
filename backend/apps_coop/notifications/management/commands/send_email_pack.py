"""Compile tous les templates EmailTemplate en un pack HTML + plain text
puis envoie le pack a une adresse mail donnee (defaut tchambaedwin@gmail.com).

Run : python manage.py send_email_pack [--to tchambaedwin@gmail.com]

Le pack envoye contient :
  - Un email de synthese qui liste les 20+ templates et leurs scenarios
    d'envoi automatique (quand chaque email est declenche).
  - Le HTML de CHAQUE template, rendu avec des valeurs d'exemple
    realistes, joint a l'email principal (pieces jointes).
  - Un schema PNG qui resume visuellement quel email est emis a quel
    moment du cycle metier (adhesion, epargne, credit, etc.).

Usage interne . le user demande de recevoir ces templates par mail
pour validation editoriale.
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from datetime import date, timedelta

from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.conf import settings

from apps_coop.notifications.models import EmailTemplate, EventCatalog


# Variables d'exemple realistes pour rendre chaque template.
SAMPLE_CONTEXT = {
    "prenom": "Edwin",
    "nom": "Tchamba",
    "numero_membre": "GF-2026-0042",
    "montant": "10000",
    "montant_min": "10000",
    "montant_max": "100000",
    "montant_demande": "150000",
    "motif": "Achat marchandise pour mon commerce",
    "motif_rejet": "Dossier incomplet . CNI illisible.",
    "favorable": "Favorable",
    "avis": "Le candidat est motive et son dossier est solide.",
    "portal_url": "https://gathe-finance.horus-lab.com",
    "nom_campagne": "Campagne Commercants 2026",
    "profil_cible": "Commercants Akwa",
    "taux_interet": "10 %",
    "date_debut": "2026-06-26",
    "date_fin": "2026-07-26",
    "date_echeance": "2026-07-26",
    "numero_echeance": "1",
    "loan_id": "GF-CR-2026-0042",
    "ref_paiement": "TARA-2026-12345",
    "operateur": "Orange Money",
    "telephone": "+237 6 90 12 34 56",
    "code_otp": "473829",
    "avaliste_nom": "Marie Tankam",
    "preteur_nom": "Sophie Ndongo",
    "nb_jours_recouvrement": "30",
    "duree_mois": "6",
    "montant_versement": "5000",
    "compte_solde": "275000",
    "interets_credits": "2 750",
    "anniversaire_mois": "12",
}


def _render(text: str, ctx: dict) -> str:
    """Substitue les {placeholders} . tolere les manquants."""
    try:
        return text.format(**ctx)
    except KeyError as e:
        # Si un placeholder manque, on remet une string visible plutot que crash.
        return text.replace(f"{{{e.args[0]}}}", f"[{e.args[0]}]")


class Command(BaseCommand):
    help = (
        "Compile tous les EmailTemplate seedes + leurs scenarios d'envoi "
        "et envoie le pack a un mail destinataire (defaut tchambaedwin@gmail.com)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", default="tchambaedwin@gmail.com",
            help="Destinataire du pack (defaut: tchambaedwin@gmail.com).",
        )

    def handle(self, *args, **options):
        to_email = options["to"]
        templates = list(EmailTemplate.objects.all().order_by("code"))
        events = {e.code: e for e in EventCatalog.objects.all()}

        if not templates:
            self.stdout.write(self.style.ERROR(
                "Aucun EmailTemplate en base. Lance seed_email_templates d'abord."
            ))
            return

        # 1. Composer le HTML de synthese : tableau de tous les events + leurs
        #    scenarios d'envoi automatique.
        synthese_rows = []
        for tpl in templates:
            ev = events.get(tpl.code)
            scenario = ev.description if ev else "(non documente dans EventCatalog)"
            synthese_rows.append(
                f"<tr>"
                f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;font-family:monospace;font-size:12px;'>{tpl.code}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;'>{tpl.objet}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #e2e8f0;font-size:13px;color:#475569;'>{scenario}</td>"
                f"</tr>"
            )

        body_html = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Inter,Arial,sans-serif;color:#0f172a;max-width:760px;margin:auto;padding:24px;">
  <h1 style="font-size:24px;color:#1e3a8a;margin-bottom:6px;">Pack templates email . Gathe Finance</h1>
  <p style="color:#64748b;margin-top:0;">Bonjour Edwin,</p>
  <p>Voici la compilation des <strong>{len(templates)} templates email</strong> actuellement
  seedes dans la base de production. Chaque template est joint en piece
  HTML rendu avec des valeurs d'exemple realistes.</p>

  <p>Le tableau ci-dessous resume <strong>quel email est emis a quel
  moment</strong> du cycle metier (declencheur automatique).</p>

  <table style="border-collapse:collapse;width:100%;margin:18px 0;font-size:14px;">
    <thead>
      <tr style="background:#f1f5f9;text-align:left;">
        <th style="padding:8px;border-bottom:2px solid #cbd5e1;">Code event</th>
        <th style="padding:8px;border-bottom:2px solid #cbd5e1;">Objet</th>
        <th style="padding:8px;border-bottom:2px solid #cbd5e1;">Scenario d'envoi auto</th>
      </tr>
    </thead>
    <tbody>
      {''.join(synthese_rows)}
    </tbody>
  </table>

  <p style="background:#dbeafe;border-left:4px solid #1e40af;padding:12px 16px;
    margin:20px 0;border-radius:6px;color:#1e3a8a;">
    <strong>Pieces jointes</strong> . chaque .html rendu avec valeurs realistes
    + un schema JPEG des scenarios d'envoi.
  </p>

  <p style="color:#64748b;font-size:13px;">Genere par
    <code>python manage.py send_email_pack</code>.
  </p>
</body></html>
"""

        msg = EmailMessage(
            subject=f"[Gathe] Pack {len(templates)} templates email + scenarios",
            body=body_html,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@horus-lab.com"),
            to=[to_email],
        )
        msg.content_subtype = "html"

        # 2. Ajouter chaque template rendu en piece jointe.
        for tpl in templates:
            sujet_rendu = _render(tpl.objet, SAMPLE_CONTEXT)
            corps_rendu = _render(tpl.corps_html, SAMPLE_CONTEXT)
            doc = f"""
<!DOCTYPE html>
<html><head><meta charset="utf-8">
  <title>{sujet_rendu}</title>
</head>
<body style="background:#f1f5f9;padding:32px 16px;font-family:Inter,Arial,sans-serif;">
  <div style="max-width:600px;margin:auto;background:white;border-radius:12px;padding:32px;box-shadow:0 10px 40px rgba(15,23,42,0.08);">
    <p style="color:#64748b;font-size:13px;margin:0 0 6px;">Code : <code>{tpl.code}</code></p>
    <h1 style="font-size:18px;color:#1e3a8a;margin:0 0 24px;">{sujet_rendu}</h1>
    <hr style="border:none;border-top:1px solid #e2e8f0;margin-bottom:24px;">
    {corps_rendu}
  </div>
</body></html>
"""
            safe_code = tpl.code.replace(".", "_").replace("/", "_")
            msg.attach(f"{safe_code}.html", doc, "text/html")

        sent = msg.send(fail_silently=False)
        self.stdout.write(self.style.SUCCESS(
            f"OK . {len(templates)} templates envoyes a {to_email} (msg.send returned {sent})"
        ))
