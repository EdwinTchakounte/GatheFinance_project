"""Idempotent seed of the transactional EmailTemplate rows.

Run with ``python manage.py seed_email_templates``. Safe to re-run — only
inserts missing codes, never overwrites an admin-edited template.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps_coop.notifications.models import EmailTemplate


TEMPLATES = [
    {
        "code": "member.welcome",
        "objet": "Bienvenue chez Gathe Finance, {prenom} !",
        "corps_html": (
            "<p>Bonjour <strong>{prenom} {nom}</strong>,</p>"
            "<p>Ta demande d'adhésion a été approuvée. Pour activer ton compte membre, "
            "il te reste à régler tes frais d'adhésion de <strong>{frais_montant} XAF</strong>.</p>"
            "<p>Connecte-toi à ton espace pour payer en quelques clics :<br>"
            "<a href=\"{portal_url}/portal/activation\">{portal_url}/portal/activation</a></p>"
            "<p>Numéro de membre : <strong>{numero_membre}</strong></p>"
            "<p>L'équipe Gathe Finance</p>"
        ),
        "variables": ["prenom", "nom", "numero_membre", "frais_montant", "portal_url"],
    },
    {
        "code": "member.activated",
        "objet": "Ton compte Gathe Finance est actif",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton paiement de <strong>{montant} XAF</strong> a été reçu, "
            "ton compte membre (n° <strong>{numero_membre}</strong>) est désormais "
            "<strong>actif</strong>.</p>"
            "<p>Tu peux maintenant utiliser tous les services : épargne, crédit, transferts.<br>"
            "<a href=\"{portal_url}/portal\">Accéder à mon espace</a></p>"
        ),
        "variables": ["prenom", "numero_membre", "montant", "portal_url"],
    },
    {
        "code": "savings.deposit_confirmed",
        "objet": "Dépôt confirmé : {montant} XAF",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton dépôt de <strong>{montant} XAF</strong> sur ton compte d'épargne a bien été enregistré.</p>"
            "<p>Nouveau solde : <strong>{solde_apres} XAF</strong></p>"
            "<p><a href=\"{portal_url}/portal\">Voir mon espace</a></p>"
        ),
        "variables": ["prenom", "montant", "solde_apres", "portal_url"],
    },
    {
        "code": "loan_request.fees_paid",
        "objet": "Frais de dossier reçus — demande #{request_id} en instruction",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Les frais de dossier de <strong>{montant} XAF</strong> pour ta demande de crédit "
            "<strong>#{request_id}</strong> ont été reçus.</p>"
            "<p>Ta demande passe maintenant en <strong>instruction</strong>. Tu recevras un email "
            "dès que le comité aura statué.</p>"
            "<p><a href=\"{portal_url}/portal/credit\">Suivre ma demande</a></p>"
        ),
        "variables": ["prenom", "request_id", "montant", "portal_url"],
    },
    {
        "code": "loan.approved",
        "objet": "Ton crédit {numero_dossier} a été approuvé",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Bonne nouvelle — le comité a approuvé ton crédit :</p>"
            "<ul>"
            "<li>Dossier : <strong>{numero_dossier}</strong></li>"
            "<li>Montant : <strong>{montant} XAF</strong></li>"
            "<li>Durée : <strong>{duree_mois} mois</strong></li>"
            "<li>Taux : <strong>{taux_pct} %/an</strong></li>"
            "<li>1<sup>re</sup> échéance : <strong>{date_premiere}</strong></li>"
            "</ul>"
            "<p>L'échéancier complet est visible dans ton espace.<br>"
            "<a href=\"{portal_url}/portal/credit\">Voir mon crédit</a></p>"
        ),
        "variables": ["prenom", "numero_dossier", "montant", "duree_mois", "taux_pct", "date_premiere", "portal_url"],
    },
    {
        "code": "loan.repayment_confirmed",
        "objet": "Remboursement de {montant} XAF reçu",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton remboursement de <strong>{montant} XAF</strong> sur le crédit "
            "<strong>{numero_dossier}</strong> a été imputé.</p>"
            "<p>Solde restant : <strong>{solde_restant} XAF</strong></p>"
            "<p><a href=\"{portal_url}/portal/credit\">Voir mon crédit</a></p>"
        ),
        "variables": ["prenom", "montant", "numero_dossier", "solde_restant", "portal_url"],
    },
    {
        "code": "booklet.ordered",
        "objet": "Commande de carnet enregistrée",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton règlement de <strong>{montant} XAF</strong> pour la commande d'un carnet "
            "d'épargne (n° membre <strong>{numero_membre}</strong>) a bien été reçu.</p>"
            "<p>L'agence procède à l'impression. Tu seras averti(e) dès que ton carnet "
            "sera disponible pour retrait.</p>"
            "<p><a href=\"{portal_url}\">Mon espace membre</a></p>"
        ),
        "variables": ["prenom", "numero_membre", "montant", "portal_url"],
    },
    {
        "code": "loan.disbursed",
        "objet": "Crédit {numero_dossier} décaissé",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton crédit <strong>{numero_dossier}</strong> d'un montant de "
            "<strong>{montant} XAF</strong> a été décaissé sur ton compte Mobile Money.</p>"
            "<p>Ta première échéance est attendue le <strong>{date_premiere}</strong>.</p>"
            "<p><a href=\"{portal_url}/credit\">Voir mon échéancier</a></p>"
        ),
        "variables": ["prenom", "numero_dossier", "montant", "date_premiere", "portal_url"],
    },
    {
        "code": "loan_renewal.approved",
        "objet": "Reconduction approuvée — nouveau dossier {nouveau_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Le comité a approuvé la reconduction de ton crédit "
            "<strong>{ancien_dossier}</strong>.</p>"
            "<ul>"
            "<li>Nouveau dossier : <strong>{nouveau_dossier}</strong></li>"
            "<li>Montant total dû : <strong>{montant_total_du} XAF</strong></li>"
            "<li>Nouvelle durée : <strong>{duree_mois} mois</strong></li>"
            "<li>Taux : <strong>{taux_pct} %/an</strong></li>"
            "<li>1<sup>re</sup> échéance : <strong>{date_premiere}</strong></li>"
            "</ul>"
            "<p>Ton échéancier complet est disponible dans ton espace.<br>"
            "<a href=\"{portal_url}/credit\">Voir mon crédit</a></p>"
        ),
        "variables": [
            "prenom", "ancien_dossier", "nouveau_dossier", "montant_total_du",
            "duree_mois", "taux_pct", "date_premiere", "portal_url",
        ],
    },
    {
        "code": "loan_renewal.rejected",
        "objet": "Reconduction du crédit {numero_dossier} — non retenue",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Le comité n'a pas retenu ta demande de reconduction du crédit "
            "<strong>{numero_dossier}</strong>.</p>"
            "<p>Motif communiqué : <em>{motif}</em></p>"
            "<p>Tu peux solliciter une nouvelle reconduction ou un nouveau crédit "
            "ultérieurement.<br><a href=\"{portal_url}/credit\">Mon espace crédit</a></p>"
        ),
        "variables": ["prenom", "numero_dossier", "motif", "portal_url"],
    },
    {
        # Cron mensuel — savings/tasks.py:crediter_interets_mensuels.
        "code": "savings.interest_credited",
        "objet": "Intérêts d'épargne crédités — {period}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Tes intérêts d'épargne pour la période <strong>{period}</strong> "
            "viennent d'être crédités : <strong>+{interets} XAF</strong> "
            "(taux de 1 %/mois, Article 4 du Règlement).</p>"
            "<p>Nouveau solde de ton compte d'épargne : <strong>{solde_apres} XAF</strong></p>"
        ),
        "variables": ["prenom", "period", "interets", "solde_apres"],
    },
    {
        # savings/services.py:_notify(wr, approved=True).
        "code": "withdrawal.approved",
        "objet": "Retrait approuvé : {montant} XAF",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ta demande de retrait de <strong>{montant} XAF</strong> a été "
            "<strong>approuvée</strong>. Le montant a été débité de ton compte "
            "d'épargne et te sera remis selon le canal convenu.</p>"
            "<p><a href=\"{portal_url}/portal\">Voir mon espace</a></p>"
        ),
        "variables": ["prenom", "montant", "portal_url"],
    },
    {
        # savings/services.py:_notify(wr, approved=False).
        "code": "withdrawal.rejected",
        "objet": "Retrait de {montant} XAF — non approuvé",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ta demande de retrait de <strong>{montant} XAF</strong> n'a pas "
            "été approuvée. Aucun montant n'a été débité de ton compte d'épargne.</p>"
            "<p>Motif communiqué : <em>{motif_rejet}</em></p>"
            "<p><a href=\"{portal_url}/portal\">Mon espace épargne</a></p>"
        ),
        "variables": ["prenom", "montant", "motif_rejet", "portal_url"],
    },
    {
        # loans/views.py — mise en demeure (Article 13).
        "code": "loan.notice",
        "objet": "Mise en demeure — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Sauf erreur de notre part, ton crédit <strong>{numero_dossier}</strong> "
            "présente un retard de remboursement. Solde restant dû : "
            "<strong>{solde_restant} XAF</strong>.</p>"
            "<p>Ceci constitue la mise en demeure n° <strong>{count}</strong> "
            "(Article 13 du Règlement). Merci de régulariser ta situation au plus vite "
            "pour éviter les pénalités de retard.</p>"
            "<p><a href=\"{portal_url}/credit\">Régler mon échéance</a></p>"
        ),
        "variables": ["prenom", "numero_dossier", "solde_restant", "count", "portal_url"],
    },
    {
        # members/services.py — reject_membership_request (Articles 1-3).
        "code": "member.rejected",
        "objet": "Ta demande d'adhésion à Gathe Finance — non retenue",
        "corps_html": (
            "<p>Bonjour {prenom} {nom},</p>"
            "<p>Après étude de ton dossier, le comité n'a pas retenu ta demande "
            "d'adhésion à la coopérative Gathe Finance.</p>"
            "<p>Motif communiqué : <em>{motif}</em></p>"
            "<p>Tu peux soumettre une nouvelle demande ultérieurement en complétant "
            "ton dossier.<br><a href=\"{portal_url}\">En savoir plus</a></p>"
            "<p>L'équipe Gathe Finance</p>"
        ),
        "variables": ["prenom", "nom", "motif", "portal_url"],
    },
    {
        # loans/views.py — loan_request_create (accusé de réception, Article 7).
        "code": "loan_request.submitted",
        "objet": "Demande de crédit reçue : {montant} XAF",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Nous avons bien reçu ta demande de crédit de "
            "<strong>{montant} XAF</strong>.</p>"
            "<p>Pour la mettre en instruction, il te reste à régler les frais de "
            "dossier de <strong>{frais_montant} XAF</strong> depuis ton espace.</p>"
            "<p><a href=\"{portal_url}/portal/credit\">Régler et suivre ma demande</a></p>"
        ),
        "variables": ["prenom", "montant", "frais_montant", "portal_url"],
    },
    {
        # loans/services.py — reject_loan_request (Article 6-7).
        "code": "loan_request.rejected",
        "objet": "Ta demande de crédit — non retenue",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Le comité a étudié ta demande de crédit et ne l'a pas retenue.</p>"
            "<p>Motif communiqué : <em>{motif}</em></p>"
            "<p>Tu peux soumettre une nouvelle demande ultérieurement.<br>"
            "<a href=\"{portal_url}/portal/credit\">Mon espace crédit</a></p>"
        ),
        "variables": ["prenom", "motif", "portal_url"],
    },
    {
        # savings/services.py — request_withdrawal (accusé de réception).
        "code": "withdrawal.requested",
        "objet": "Demande de retrait reçue : {montant} XAF",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ta demande de retrait de <strong>{montant} XAF</strong> a bien été "
            "enregistrée. Elle est en attente de la décision de l'administration ; "
            "aucun montant n'a encore été débité.</p>"
            "<p>Tu recevras un email dès qu'une décision sera prise.<br>"
            "<a href=\"{portal_url}/portal\">Voir mon espace</a></p>"
        ),
        "variables": ["prenom", "montant", "portal_url"],
    },
    {
        # loans/views.py — loan_renewal_request (accusé de réception, Article 10).
        "code": "loan_renewal.requested",
        "objet": "Demande de reconduction reçue — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ta demande de reconduction du crédit <strong>{numero_dossier}</strong> "
            "(prorogation de <strong>{duree_mois} mois</strong>, Article 10) a bien "
            "été enregistrée et part en décision du comité.</p>"
            "<p>Tu recevras un email dès que le comité aura statué.<br>"
            "<a href=\"{portal_url}/portal/credit\">Suivre ma demande</a></p>"
        ),
        "variables": ["prenom", "numero_dossier", "duree_mois", "portal_url"],
    },
    {
        # loans/tasks.py — suivi_retards_quotidien, échéance passée en retard
        # + pénalité 50 % (Articles 12-13).
        "code": "loan.installment_overdue",
        "objet": "Échéance en retard — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>L'échéance n° <strong>{numero_echeance}</strong> de ton crédit "
            "<strong>{numero_dossier}</strong> (<strong>{montant_du} XAF</strong>) "
            "est arrivée à échéance sans règlement complet.</p>"
            "<p>Conformément à l'Article 12 du Règlement, une pénalité de retard de "
            "<strong>{penalite} XAF</strong> (50 % des intérêts dus) a été appliquée.</p>"
            "<p>Merci de régulariser au plus vite pour éviter d'autres pénalités.<br>"
            "<a href=\"{portal_url}/portal/credit\">Régler mon échéance</a></p>"
        ),
        "variables": [
            "prenom", "numero_dossier", "numero_echeance", "montant_du",
            "penalite", "portal_url",
        ],
    },
    {
        # loans/tasks.py — rappel_echeances_proches (rappel J-3, proactif).
        "code": "loan.installment_due_soon",
        "objet": "Rappel : échéance le {date_echeance} — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Un petit rappel amical : l'échéance de ton crédit "
            "<strong>{numero_dossier}</strong> d'un montant de "
            "<strong>{montant_echeance} XAF</strong> est attendue le "
            "<strong>{date_echeance}</strong>.</p>"
            "<p>Pense à provisionner ton règlement pour éviter toute pénalité de "
            "retard.<br><a href=\"{portal_url}/portal/credit\">Régler maintenant</a></p>"
        ),
        "variables": [
            "prenom", "numero_dossier", "montant_echeance", "date_echeance", "portal_url",
        ],
    },
    {
        # A2 — Alerte douce J-N avant l'anniversaire annuel d'adhésion.
        "code": "member.reinscription_due",
        "objet": "Réinscription annuelle — bientôt {date_anniversaire}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ton anniversaire d'adhésion à Gathé Finance approche : "
            "<strong>{date_anniversaire}</strong> (dans {lead_days} jours).</p>"
            "<p>Pour rester à jour, pense à confirmer ta réinscription auprès "
            "de l'agence ou via le portail.</p>"
            "<p>Numéro membre : <strong>{numero_membre}</strong></p>"
        ),
        "variables": [
            "prenom", "numero_membre", "date_anniversaire", "lead_days",
        ],
    },
    {
        # A2 — Confirmation par l'admin que la réinscription a été actée.
        "code": "member.reinscription_confirmed",
        "objet": "Réinscription confirmée — merci {prenom}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Ta réinscription annuelle a bien été enregistrée le "
            "<strong>{date_confirmation}</strong>.</p>"
            "<p>La prochaine échéance est désormais fixée au "
            "<strong>{prochaine_echeance}</strong>.</p>"
            "<p>Numéro membre : <strong>{numero_membre}</strong></p>"
        ),
        "variables": [
            "prenom", "numero_membre", "date_confirmation", "prochaine_echeance",
        ],
    },
    {
        # Cycle contentieux — pénalité globale appliquée (J = date limite globale).
        "code": "loan.penalite_globale_appliquee",
        "objet": "Pénalité appliquée — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>La date limite de remboursement de ton crédit "
            "<strong>{numero_dossier}</strong> a été franchie sans que le solde "
            "ne soit régularisé.</p>"
            "<p>Une pénalité de <strong>{penalite} XAF</strong> a été ajoutée à "
            "ton solde, qui est désormais de <strong>{nouveau_solde} XAF</strong>.</p>"
            "<p><strong>Tu disposes de {delai_grace_jours} jours</strong> pour "
            "régulariser, faute de quoi le solde sera prélevé automatiquement "
            "sur ton épargne.</p>"
        ),
        "variables": [
            "prenom", "numero_dossier", "penalite", "nouveau_solde", "delai_grace_jours",
        ],
    },
    {
        # Cycle contentieux — saisie épargne automatique (R1) effectuée.
        "code": "loan.savings_seized",
        "objet": "Prélèvement automatique sur ton épargne — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Conformément aux conditions de ton crédit "
            "<strong>{numero_dossier}</strong>, la cooperative a prélevé "
            "<strong>{montant_saisi} XAF</strong> sur ton compte d'épargne "
            "pour couvrir le solde restant impayé.</p>"
            "<p>Solde restant à payer après prélèvement : "
            "<strong>{solde_restant_apres} XAF</strong>.</p>"
            "<p>Si ce montant est non nul, le dossier est transmis au "
            "recouvrement contentieux.</p>"
        ),
        "variables": [
            "prenom", "numero_dossier", "montant_saisi", "solde_restant_apres",
        ],
    },
    {
        # Cycle contentieux — poursuites engagées (épargne insuffisante).
        "code": "loan.poursuite_engaged",
        "objet": "Recouvrement contentieux — crédit {numero_dossier}",
        "corps_html": (
            "<p>Bonjour {prenom},</p>"
            "<p>Suite au prélèvement sur ton épargne, un reliquat de "
            "<strong>{reliquat} XAF</strong> reste dû au titre du crédit "
            "<strong>{numero_dossier}</strong>.</p>"
            "<p>Le dossier est désormais transmis à notre service "
            "contentieux/juridique pour recouvrement.</p>"
            "<p>Tu peux à tout moment contacter l'agence pour proposer un "
            "plan d'apurement amiable.</p>"
        ),
        "variables": ["prenom", "numero_dossier", "reliquat"],
    },
]


class Command(BaseCommand):
    help = "Seed the transactional email templates used by the business hooks (idempotent)."

    def handle(self, *args, **options):
        created = 0
        existed = 0
        for spec in TEMPLATES:
            obj, was_created = EmailTemplate.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "objet": spec["objet"],
                    "corps_html": spec["corps_html"],
                    "variables": spec["variables"],
                    "actif": True,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {obj.code}"))
            else:
                existed += 1
                self.stdout.write(f"  · {obj.code} (déjà présent)")
        self.stdout.write(self.style.SUCCESS(f"\n{created} créé(s), {existed} déjà en base."))
