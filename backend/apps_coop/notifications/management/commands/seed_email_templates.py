"""Idempotent seed of the transactional EmailTemplate rows.

Run with ``python manage.py seed_email_templates`` - par défaut idempotent
(get_or_create). Ajouter ``--force`` pour réécrire les templates existants
quand le design global change (ex. refonte 2026-06-18).

Le wrapper visuel (header aurore + footer brand) est appliqué au moment
de l'envoi par ``services._wrap_layout`` - ici on définit uniquement le
``corps_html`` central.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps_coop.notifications.email_blocks import (
    amount,
    callout,
    closing,
    code_block,
    cta,
    cta_secondary,
    hi,
    info_card,
    lead,
    p,
    title,
)
from apps_coop.notifications.models import EmailTemplate


def _join(*parts: str) -> str:
    """Concatène les blocs avec un séparateur vide."""
    return "".join(parts)


# Toutes les templates utilisent ``hi("{prenom}")`` comme salutation
# d'ouverture. Les placeholders entre accolades sont injectés au moment
# de l'envoi via ``str.format(**context)``.

TEMPLATES = [
    # ────────────────────────────────────────────────────────────────────
    # ADHÉSION (3 templates)
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "member.welcome",
        "objet": "Bienvenue chez GATHE Finance, {prenom} !",
        "corps_html": _join(
            hi("{nom_complet}"),
            title("Ta demande d'adhésion est approuvée"),
            lead(
                "Bonne nouvelle - le comité a validé ton dossier. Avant tout, "
                "définis ton mot de passe pour accéder à ton espace membre, "
                "puis règle tes frais d'activation pour ouvrir ton compte."
            ),
            info_card([
                ("Numéro membre", "<strong>{numero_membre}</strong>"),
                ("Frais d'adhésion", "<strong>{frais_adhesion} XAF</strong>"),
                ("Frais d'inscription", "<strong>{frais_inscription} XAF</strong>"),
                ("Frais de carnet", "<strong>{frais_carnet} XAF</strong>"),
                ("Total à régler", "<strong>{frais_montant} XAF</strong>"),
                ("Validité", "Activation immédiate après paiement"),
            ], tone="success"),
            cta("Définir mon mot de passe", "{password_setup_url}"),
            p(
                "Ces trois frais (adhésion, inscription et carnet) sont "
                "distincts et exigés une seule fois pour activer ton compte. "
                "Ce lien est valable <strong>72 heures</strong>. Après avoir "
                "défini ton mot de passe, tu pourras te connecter au portail ou "
                "à l'application mobile, puis régler tes frais par Mobile Money "
                "ou en espèces à l'agence Akwa Bercy."
            ),
            cta_secondary("Régler mes frais (après connexion)", "{portal_url}/portal/activation"),
            closing(),
        ),
        "variables": [
            "prenom", "nom", "nom_complet", "numero_membre", "frais_montant",
            "frais_adhesion", "frais_inscription", "frais_carnet",
            "portal_url", "password_setup_url",
        ],
    },
    {
        "code": "member.activated",
        "objet": "Ton compte GATHE Finance est actif",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton compte est désormais actif"),
            lead(
                "Ton paiement de <strong>{montant} XAF</strong> a bien été reçu. "
                "Ton compte membre <strong>{numero_membre}</strong> est maintenant "
                "actif - tous les services de la coopérative te sont ouverts."
            ),
            info_card([
                ("Épargne", "Dépôts &amp; intérêts mensuels 1 %"),
                ("Crédit", "BRC, avaliste, microcampagnes"),
                ("Cotisations", "Journalière, hebdomadaire ou mensuelle"),
            ], tone="success"),
            cta("Accéder à mon espace", "{portal_url}/portal"),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "montant", "portal_url"],
    },
    {
        "code": "member.rejected",
        "objet": "Ta demande d'adhésion à GATHE Finance",
        "corps_html": _join(
            hi("{prenom} {nom}"),
            title("Ta demande n'a pas été retenue"),
            lead(
                "Après étude de ton dossier, le comité n'a pas pu retenir ta "
                "demande d'adhésion à la coopérative pour le moment."
            ),
            callout("<strong>Motif communiqué :</strong> {motif}", tone="warn"),
            p(
                "Tu peux soumettre une nouvelle demande ultérieurement en "
                "complétant ton dossier ou en sollicitant un entretien avec "
                "l'agence."
            ),
            cta_secondary("En savoir plus", "{portal_url}"),
            closing(),
        ),
        "variables": ["prenom", "nom", "motif", "portal_url"],
    },
    {
        "code": "membership.interview_scheduled",
        "objet": "Ton entretien d'admission à GATHE Finance",
        "corps_html": _join(
            hi("{prenom} {nom}"),
            title("Ton entretien d'admission a été enregistré"),
            lead(
                "Conformément à l'Article 3 du Règlement, le comité a tenu "
                "ton entretien d'admission. Voici l'avis transmis."
            ),
            callout(
                "<strong>Issue :</strong> {favorable}<br/>"
                "<strong>Avis du comité :</strong> {avis}",
                tone="info",
            ),
            p(
                "La décision finale (approbation ou rejet) te sera notifiée "
                "par e-mail dans les jours qui suivent."
            ),
            cta_secondary("Suivre ma demande", "{portal_url}"),
            closing(),
        ),
        "variables": ["prenom", "nom", "favorable", "avis", "portal_url"],
    },
    {
        "code": "campaign.created",
        "objet": "Nouvelle campagne micro-crédit · {nom_campagne}",
        "corps_html": _join(
            hi("{prenom} {nom}"),
            title("Nouvelle opportunité de financement"),
            lead(
                "La coopérative ouvre une nouvelle campagne micro-crédit. "
                "Si tu remplis les critères, tu peux postuler depuis l'app."
            ),
            callout(
                "<strong>Campagne :</strong> {nom_campagne}<br/>"
                "<strong>Profil ciblé :</strong> {profil_cible}<br/>"
                "<strong>Montant :</strong> {montant_min} à {montant_max} XAF<br/>"
                "<strong>Période :</strong> {date_debut} au {date_fin}",
                tone="info",
            ),
            p(
                "Ouvre l'application GATHE Finance et rends-toi dans l'écran "
                "Crédit pour postuler tant que la campagne reste ouverte."
            ),
            closing(),
        ),
        "variables": [
            "prenom", "nom", "nom_campagne", "profil_cible",
            "montant_min", "montant_max", "taux_interet",
            "date_debut", "date_fin",
        ],
    },
    # ────────────────────────────────────────────────────────────────────
    # ÉPARGNE (3 templates)
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "savings.deposit_confirmed",
        "objet": "Dépôt confirmé · {montant} XAF",
        "corps_html": _join(
            hi("{prenom}"),
            title("Dépôt enregistré"),
            lead(
                "Ton versement a bien été crédité sur ton compte d'épargne."
            ),
            amount("{montant}", label="Montant déposé"),
            info_card([
                ("Nouveau solde", "<strong>{solde_apres} XAF</strong>"),
                ("Taux d'intérêt mensuel", "1 % (Art. 4 du Règlement)"),
            ], tone="success"),
            cta("Voir mon espace", "{portal_url}/portal"),
            closing(),
        ),
        "variables": ["prenom", "montant", "solde_apres", "portal_url"],
    },
    {
        "code": "savings.interest_credited",
        "objet": "Intérêts d'épargne crédités - {period}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Tes intérêts sont crédités"),
            lead(
                "Tes intérêts d'épargne pour la période <strong>{period}</strong> "
                "viennent d'être ajoutés à ton solde."
            ),
            amount("+{interets}", label="Intérêts crédités"),
            info_card([
                ("Période", "{period}"),
                ("Taux mensuel", "1 % (Article 4)"),
                ("Nouveau solde", "<strong>{solde_apres} XAF</strong>"),
            ], tone="success"),
            closing(),
        ),
        "variables": ["prenom", "period", "interets", "solde_apres"],
    },
    {
        "code": "withdrawal.requested",
        "objet": "Demande de retrait reçue · {montant} XAF",
        "corps_html": _join(
            hi("{prenom}"),
            title("Demande de retrait enregistrée"),
            lead(
                "Ta demande de retrait a bien été reçue. Elle est en attente "
                "de validation par l'administration ; aucun montant n'a encore "
                "été débité de ton compte."
            ),
            amount("{montant}", label="Montant demandé"),
            callout(
                "Tu recevras un email dès qu'une décision sera prise - "
                "généralement sous 24 à 48 heures ouvrables.",
                tone="info",
            ),
            cta("Voir mon espace", "{portal_url}/portal"),
            closing(),
        ),
        "variables": ["prenom", "montant", "portal_url"],
    },
    {
        "code": "withdrawal.approved",
        "objet": "Retrait approuvé · {montant} XAF",
        "corps_html": _join(
            hi("{prenom}"),
            title("Retrait approuvé"),
            lead(
                "Ta demande de retrait a été <strong>validée</strong>. Le montant "
                "a été débité de ton compte d'épargne et te sera remis selon le "
                "canal convenu."
            ),
            amount("{montant}", label="Montant remis"),
            cta("Voir mon historique", "{portal_url}/portal"),
            closing(),
        ),
        "variables": ["prenom", "montant", "portal_url"],
    },
    {
        "code": "withdrawal.rejected",
        "objet": "Retrait de {montant} XAF non approuvé",
        "corps_html": _join(
            hi("{prenom}"),
            title("Retrait non approuvé"),
            lead(
                "Ta demande de retrait de <strong>{montant} XAF</strong> n'a pas "
                "été approuvée. <strong>Aucun montant n'a été débité</strong> de "
                "ton compte d'épargne."
            ),
            callout("<strong>Motif :</strong> {motif_rejet}", tone="warn"),
            cta_secondary("Mon espace épargne", "{portal_url}/portal"),
            closing(),
        ),
        "variables": ["prenom", "montant", "motif_rejet", "portal_url"],
    },
    # ────────────────────────────────────────────────────────────────────
    # CRÉDIT - demande, approbation, décaissement, remboursement
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "loan_request.submitted",
        "objet": "Demande de crédit reçue · {montant} XAF",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ta demande est enregistrée"),
            lead(
                "Nous avons bien reçu ta demande de crédit. Pour la mettre en "
                "instruction, il te reste à régler les frais de dossier depuis "
                "ton espace."
            ),
            info_card([
                ("Montant demandé", "<strong>{montant} XAF</strong>"),
                ("Frais de dossier", "<strong>{frais_montant} XAF</strong>"),
                ("Statut", "En attente de paiement des frais"),
            ], tone="info"),
            cta("Régler et suivre ma demande", "{portal_url}/portal/credit"),
            p(
                "Les frais sont non-remboursables (Article 7 du Règlement). Le "
                "comité statue dans un délai de 7 jours ouvrés après leur "
                "réception."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant", "frais_montant", "portal_url"],
    },
    {
        "code": "loan_request.fees_paid",
        "objet": "Frais reçus - demande #{request_id} en instruction",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ta demande passe en instruction"),
            lead(
                "Les frais de dossier de <strong>{montant} XAF</strong> pour ta "
                "demande de crédit <strong>#{request_id}</strong> ont bien été "
                "reçus. Le comité étudie maintenant ton dossier."
            ),
            callout(
                "Tu recevras un email dès que le comité aura statué, "
                "généralement sous 7 jours ouvrés.",
                tone="info",
            ),
            cta("Suivre ma demande", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "request_id", "montant", "portal_url"],
    },
    {
        "code": "loan_request.rejected",
        "objet": "Ta demande de crédit n'a pas été retenue",
        "corps_html": _join(
            hi("{prenom}"),
            title("Demande non retenue"),
            lead(
                "Après étude de ton dossier, le comité n'a pas retenu ta "
                "demande de crédit."
            ),
            callout("<strong>Motif :</strong> {motif}", tone="warn"),
            p(
                "Tu peux soumettre une nouvelle demande après avoir tenu compte "
                "des remarques. N'hésite pas à solliciter un entretien à l'agence "
                "pour préparer ton prochain dossier."
            ),
            cta_secondary("Mon espace crédit", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "motif", "portal_url"],
    },
    {
        "code": "loan.approved",
        "objet": "Ton crédit {numero_dossier} est approuvé",
        "corps_html": _join(
            hi("{prenom}"),
            title("Bonne nouvelle - ton crédit est approuvé"),
            lead(
                "Le comité a validé ton crédit. Voici les conditions retenues :"
            ),
            info_card([
                ("Dossier", "<strong>{numero_dossier}</strong>"),
                ("Montant", "<strong>{montant} XAF</strong>"),
                ("Durée", "{duree_mois} mois"),
                ("Taux", "{taux_pct} %/an"),
                ("1<sup>re</sup> échéance", "<strong>{date_premiere}</strong>"),
            ], tone="success"),
            cta("Voir mon échéancier", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_dossier", "montant", "duree_mois",
            "taux_pct", "date_premiere", "portal_url",
        ],
    },
    {
        "code": "loan.disbursed",
        "objet": "Crédit {numero_dossier} décaissé",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton crédit a été décaissé"),
            lead(
                "Ton crédit a été versé sur ton compte Mobile Money. Les fonds "
                "devraient être disponibles dans les prochaines minutes."
            ),
            amount("{montant}", label="Montant versé"),
            info_card([
                ("Dossier", "<strong>{numero_dossier}</strong>"),
                ("1<sup>re</sup> échéance", "<strong>{date_premiere}</strong>"),
                ("Note de demande PDF", "Disponible dans ton espace"),
            ], tone="success"),
            cta("Voir mon échéancier", "{portal_url}/credit"),
            closing(),
        ),
        "variables": ["prenom", "numero_dossier", "montant", "date_premiere", "portal_url"],
    },
    {
        "code": "loan.repayment_confirmed",
        "objet": "Remboursement de {montant} XAF reçu",
        "corps_html": _join(
            hi("{prenom}"),
            title("Remboursement enregistré"),
            lead(
                "Ton remboursement a bien été imputé sur ton crédit "
                "<strong>{numero_dossier}</strong>. Merci pour ta régularité."
            ),
            amount("{montant}", label="Montant remboursé"),
            info_card([
                ("Solde restant", "<strong>{solde_restant} XAF</strong>"),
                ("Imputation", "FIFO sur tes échéances ouvertes"),
            ], tone="success"),
            cta("Voir mon crédit", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "montant", "numero_dossier", "solde_restant", "portal_url"],
    },
    # ────────────────────────────────────────────────────────────────────
    # RECONDUCTION
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "loan_renewal.requested",
        "objet": "Demande de reconduction enregistrée · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Reconduction enregistrée"),
            lead(
                "Ta demande de reconduction du crédit "
                "<strong>{numero_dossier}</strong> (prorogation de "
                "<strong>{duree_mois} mois</strong>, Article 10) part en "
                "décision du comité."
            ),
            callout(
                "Tu recevras un email dès que le comité aura statué.",
                tone="info",
            ),
            cta("Suivre ma demande", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "numero_dossier", "duree_mois", "portal_url"],
    },
    {
        "code": "loan_renewal.approved",
        "objet": "Reconduction approuvée · {nouveau_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ta reconduction est approuvée"),
            lead(
                "Le comité a validé la reconduction de ton crédit "
                "<strong>{ancien_dossier}</strong>. Un nouveau dossier prend le "
                "relais avec un échéancier ajusté."
            ),
            info_card([
                ("Nouveau dossier", "<strong>{nouveau_dossier}</strong>"),
                ("Montant total dû", "<strong>{montant_total_du} XAF</strong>"),
                ("Nouvelle durée", "{duree_mois} mois"),
                ("Taux", "{taux_pct} %/an"),
                ("1<sup>re</sup> échéance", "<strong>{date_premiere}</strong>"),
            ], tone="success"),
            cta("Voir mon crédit", "{portal_url}/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "ancien_dossier", "nouveau_dossier", "montant_total_du",
            "duree_mois", "taux_pct", "date_premiere", "portal_url",
        ],
    },
    {
        "code": "loan_renewal.rejected",
        "objet": "Reconduction non retenue · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Reconduction non retenue"),
            lead(
                "Le comité n'a pas retenu ta demande de reconduction du crédit "
                "<strong>{numero_dossier}</strong>."
            ),
            callout("<strong>Motif :</strong> {motif}", tone="warn"),
            p(
                "Tu peux solliciter une nouvelle reconduction ou un nouveau "
                "crédit ultérieurement."
            ),
            cta_secondary("Mon espace crédit", "{portal_url}/credit"),
            closing(),
        ),
        "variables": ["prenom", "numero_dossier", "motif", "portal_url"],
    },
    # ────────────────────────────────────────────────────────────────────
    # RETARDS, PÉNALITÉS, CONTENTIEUX
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "loan.installment_due_soon",
        "objet": "Rappel : échéance le {date_echeance} · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Petit rappel d'échéance"),
            lead(
                "L'échéance de ton crédit <strong>{numero_dossier}</strong> "
                "est attendue prochainement. Pense à provisionner ton règlement "
                "pour éviter toute pénalité."
            ),
            info_card([
                ("Date d'échéance", "<strong>{date_echeance}</strong>"),
                ("Montant attendu", "<strong>{montant_echeance} XAF</strong>"),
            ], tone="info"),
            cta("Régler maintenant", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_dossier", "montant_echeance", "date_echeance", "portal_url",
        ],
    },
    {
        "code": "loan.installment_overdue",
        "objet": "Échéance en retard · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Une échéance est en retard"),
            lead(
                "L'échéance n° <strong>{numero_echeance}</strong> de ton crédit "
                "<strong>{numero_dossier}</strong> est arrivée à échéance sans "
                "règlement complet."
            ),
            info_card([
                ("Montant dû", "<strong>{montant_du} XAF</strong>"),
                ("Pénalité (Art. 12)", "<strong>{penalite} XAF</strong>"),
                ("Régulariser sous", "48 heures"),
            ], tone="danger"),
            callout(
                "Conformément à l'Article 12, une pénalité de 50 % des "
                "intérêts dus a été appliquée. Régularise rapidement pour "
                "éviter d'autres pénalités.",
                tone="warn",
            ),
            cta("Régler mon échéance", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_dossier", "numero_echeance", "montant_du",
            "penalite", "portal_url",
        ],
    },
    {
        "code": "loan.notice",
        "objet": "Mise en demeure · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Mise en demeure n° {count}"),
            lead(
                "Sauf erreur de notre part, ton crédit "
                "<strong>{numero_dossier}</strong> présente un retard de "
                "remboursement persistant."
            ),
            info_card([
                ("Solde restant dû", "<strong>{solde_restant} XAF</strong>"),
                ("Mise en demeure", "n° {count}"),
                ("Base réglementaire", "Article 13"),
            ], tone="danger"),
            p(
                "Merci de régulariser ta situation au plus vite pour éviter "
                "l'application des pénalités prévues à l'Article 13 et le "
                "transfert du dossier au recouvrement contentieux."
            ),
            cta("Régulariser maintenant", "{portal_url}/credit"),
            closing(),
        ),
        "variables": ["prenom", "numero_dossier", "solde_restant", "count", "portal_url"],
    },
    {
        "code": "loan.penalite_globale_appliquee",
        "objet": "Pénalité appliquée · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Date limite dépassée"),
            lead(
                "La date limite globale de remboursement de ton crédit "
                "<strong>{numero_dossier}</strong> a été franchie sans que le "
                "solde ne soit régularisé."
            ),
            info_card([
                ("Pénalité ajoutée", "<strong>{penalite} XAF</strong>"),
                ("Nouveau solde dû", "<strong>{nouveau_solde} XAF</strong>"),
                ("Délai de grâce", "{delai_grace_jours} jours"),
            ], tone="danger"),
            callout(
                "Passé le délai de grâce, le solde sera <strong>prélevé "
                "automatiquement</strong> sur ton compte d'épargne (R1).",
                tone="warn",
            ),
            closing(),
        ),
        "variables": [
            "prenom", "numero_dossier", "penalite", "nouveau_solde", "delai_grace_jours",
        ],
    },
    {
        "code": "loan.savings_seized",
        "objet": "Prélèvement sur épargne · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Prélèvement automatique effectué"),
            lead(
                "Conformément aux conditions de ton crédit "
                "<strong>{numero_dossier}</strong>, la coopérative a prélevé "
                "le montant ci-dessous sur ton compte d'épargne pour couvrir "
                "le solde impayé."
            ),
            amount("{montant_saisi}", label="Montant prélevé sur épargne"),
            info_card([
                ("Solde restant à payer", "<strong>{solde_restant_apres} XAF</strong>"),
            ], tone="danger"),
            p(
                "Si un reliquat subsiste, le dossier est transmis au "
                "recouvrement contentieux."
            ),
            closing(),
        ),
        "variables": [
            "prenom", "numero_dossier", "montant_saisi", "solde_restant_apres",
        ],
    },
    {
        "code": "loan.poursuite_engaged",
        "objet": "Recouvrement contentieux · {numero_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Dossier transmis au contentieux"),
            lead(
                "Suite au prélèvement sur ton épargne, un reliquat reste dû au "
                "titre du crédit <strong>{numero_dossier}</strong>."
            ),
            amount("{reliquat}", label="Reliquat dû"),
            callout(
                "Tu peux à tout moment contacter l'agence pour proposer un "
                "plan d'apurement amiable avant l'engagement des poursuites.",
                tone="warn",
            ),
            closing(),
        ),
        "variables": ["prenom", "numero_dossier", "reliquat"],
    },
    # ────────────────────────────────────────────────────────────────────
    # AVALISTE (LOT 10)
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "loan.avaliste_consent_requested",
        "objet": "Demande de caution - {borrower_nom}",
        "corps_html": _join(
            hi("{prenom}"),
            title("On te désigne comme avaliste"),
            lead(
                "<strong>{borrower_nom}</strong> (membre {borrower_numero}) "
                "t'a désigné comme avaliste pour sa demande de crédit. En "
                "acceptant, tu t'engages à couvrir le remboursement en cas de "
                "défaut, dans la limite de ton épargne disponible."
            ),
            info_card([
                ("Demandeur", "{borrower_nom} ({borrower_numero})"),
                ("Montant garanti", "<strong>{montant} XAF</strong>"),
                ("Toi (avaliste)", "Membre {avaliste_numero}"),
            ], tone="info"),
            cta("Accepter ou refuser", "{portal_url}/portal/avaliste"),
            p(
                "Prends ton temps - cette désignation n'est validée qu'après "
                "ton consentement explicite depuis ton espace membre."
            ),
            closing(),
        ),
        "variables": [
            "prenom", "borrower_nom", "borrower_numero", "montant",
            "avaliste_numero", "portal_url",
        ],
    },
    {
        "code": "loan.avaliste_consent_accepted",
        "objet": "Ton avaliste a accepté ✓",
        "corps_html": _join(
            hi("{prenom}"),
            title("L'avaliste a accepté"),
            lead(
                "L'avaliste que tu as désigné (membre "
                "<strong>{avaliste_numero}</strong>) a <strong>accepté</strong> "
                "de se porter caution pour ta demande de crédit."
            ),
            info_card([
                ("Montant garanti", "<strong>{montant} XAF</strong>"),
                ("Statut demande", "Transmise au comité"),
            ], tone="success"),
            cta("Suivre ma demande", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "borrower_nom", "borrower_numero", "montant",
            "avaliste_numero", "portal_url",
        ],
    },
    {
        "code": "loan.avaliste_consent_refused",
        "objet": "Caution refusée - désigne un autre avaliste",
        "corps_html": _join(
            hi("{prenom}"),
            title("L'avaliste a refusé"),
            lead(
                "L'avaliste que tu as désigné (membre "
                "<strong>{avaliste_numero}</strong>) n'a pas souhaité se porter "
                "caution. Pas de souci - tu peux désigner un autre membre pour "
                "relancer ta demande."
            ),
            cta("Désigner un autre avaliste", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": [
            "prenom", "borrower_nom", "borrower_numero", "montant",
            "avaliste_numero", "portal_url",
        ],
    },
    # ────────────────────────────────────────────────────────────────────
    # FUNDING 24h prêteur (LOT 8)
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "loan.funding.consent_requested",
        "objet": "Crédit à financer · {montant_propose} XAF (24h)",
        "corps_html": _join(
            hi("{prenom}"),
            title("Un crédit à financer"),
            lead(
                "En tant que prêteur de la coopérative, on te propose de "
                "participer au financement du crédit "
                "<strong>{loan_dossier}</strong>. Tu reçois en contrepartie "
                "ta part d'intérêts selon la règle 50/50 (Article 6)."
            ),
            info_card([
                ("Tranche proposée", "<strong>{montant_propose} XAF</strong>"),
                ("Décision avant", "<strong>{deadline}</strong>"),
                ("Sans réponse", "Tranche acceptée par défaut"),
            ], tone="info"),
            cta("Voir et décider", "{portal_url}/portal/preteur"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_membre", "loan_dossier", "montant_propose",
            "deadline", "portal_url",
        ],
    },
    {
        "code": "loan.funding.completed",
        "objet": "Crédit {loan_dossier} financé - décaissement en cours",
        "corps_html": _join(
            hi("{prenom}"),
            title("Financement complet"),
            lead(
                "Excellente nouvelle - le financement de ton crédit "
                "<strong>{loan_dossier}</strong> est complet."
            ),
            amount("{montant}", label="Montant financé"),
            callout(
                "La coopérative procède au décaissement vers ton compte "
                "Mobile Money. Tu recevras un second email dès que les fonds "
                "seront disponibles.",
                tone="success",
            ),
            cta("Suivre mon crédit", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "loan_dossier", "montant", "portal_url"],
    },
    {
        "code": "loan.funding.exhausted",
        "objet": "Financement insuffisant · {loan_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Financement insuffisant"),
            lead(
                "Malgré plusieurs vagues de sollicitation des prêteurs, "
                "l'épargne-prêteur disponible n'a pas permis de financer "
                "intégralement ton crédit <strong>{loan_dossier}</strong>."
            ),
            info_card([
                ("Déficit de financement", "<strong>{deficit} XAF</strong>"),
                ("Prochaine étape", "Contact de la coopérative"),
            ], tone="warn"),
            p(
                "La coopérative te contactera pour proposer une solution : "
                "montant ajusté, report ou alternative."
            ),
            cta_secondary("Mon espace crédit", "{portal_url}/portal/credit"),
            closing(),
        ),
        "variables": ["prenom", "loan_dossier", "deficit", "portal_url"],
    },
    # A5 . Engagement d'une tranche preteur (composer funding manuel admin).
    # Mail envoye juste apres engagement et AVANT que les interets ne commencent.
    {
        "code": "lender.tranche_engaged",
        "objet": "Ton placement de {montant_engage} XAF vient d'être engagé",
        "corps_html": _join(
            hi("{prenom}"),
            title("Placement engagé dans un crédit"),
            lead(
                "L'administration vient d'engager une partie de ton épargne "
                "placement pour financer le crédit "
                "<strong>{loan_dossier}</strong> au profit de "
                "<strong>{beneficiaire_label}</strong>."
            ),
            info_card([
                ("Montant engagé", "<strong>{montant_engage} XAF</strong>"),
                ("Crédit financé", "<strong>{loan_dossier}</strong>"),
                ("Bénéficiaire", "{beneficiaire_label}"),
                ("Date d'engagement", "{date_engagement}"),
                ("Début des intérêts", "À partir d'aujourd'hui"),
            ], tone="info"),
            p(
                "Les intérêts seront calculés sur cette portion engagée "
                "uniquement, selon la règle 50/50 (Article 6) sur chaque "
                "remboursement du crédit financé."
            ),
            cta("Voir mon espace prêteur", "{portal_url}/portal/preteur"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_membre", "loan_dossier", "beneficiaire_label",
            "montant_engage", "date_engagement", "portal_url",
        ],
    },
    # ────────────────────────────────────────────────────────────────────
    # CARNET, RÉINSCRIPTION, AUTH
    # ────────────────────────────────────────────────────────────────────
    {
        "code": "booklet.ordered",
        "objet": "Commande de carnet enregistrée",
        "corps_html": _join(
            hi("{prenom}"),
            title("Commande de carnet reçue"),
            lead(
                "Ton règlement pour la commande d'un carnet d'épargne (n° "
                "membre <strong>{numero_membre}</strong>) a bien été reçu. "
                "L'agence procède à l'impression."
            ),
            amount("{montant}", label="Montant réglé"),
            callout(
                "Tu seras averti(e) par email dès que ton carnet sera "
                "disponible pour retrait à l'agence.",
                tone="info",
            ),
            cta_secondary("Mon espace membre", "{portal_url}"),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "montant", "portal_url"],
    },
    {
        "code": "member.reinscription_due",
        "objet": "Réinscription annuelle bientôt due · {date_anniversaire}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Réinscription annuelle approche"),
            lead(
                "Ton anniversaire d'adhésion à GATHE Finance approche. Pour "
                "rester à jour, pense à confirmer ta réinscription auprès de "
                "l'agence ou via ton espace."
            ),
            info_card([
                ("Anniversaire", "<strong>{date_anniversaire}</strong>"),
                ("Dans", "{lead_days} jours"),
                ("Numéro membre", "<strong>{numero_membre}</strong>"),
            ], tone="info"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_membre", "date_anniversaire", "lead_days",
        ],
    },
    {
        "code": "member.reinscription_confirmed",
        "objet": "Réinscription confirmée - merci !",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ta réinscription est confirmée"),
            lead(
                "Ta réinscription annuelle a été enregistrée. Tu es à jour "
                "pour l'année qui vient."
            ),
            info_card([
                ("Date de confirmation", "<strong>{date_confirmation}</strong>"),
                ("Prochaine échéance", "<strong>{prochaine_echeance}</strong>"),
                ("Numéro membre", "<strong>{numero_membre}</strong>"),
            ], tone="success"),
            closing(),
        ),
        "variables": [
            "prenom", "numero_membre", "date_confirmation", "prochaine_echeance",
        ],
    },
    {
        "code": "auth.password_reset_otp",
        "objet": "Ton code de réinitialisation GATHE Finance",
        "corps_html": _join(
            hi("{prenom}"),
            title("Réinitialisation de ton mot de passe"),
            lead(
                "Tu as demandé la réinitialisation de ton mot de passe. "
                "Utilise le code ci-dessous pour confirmer."
            ),
            code_block("{code}"),
            callout(
                "Ce code est valable <strong>{ttl_minutes} minutes</strong> "
                "et ne peut être utilisé qu'une seule fois.",
                tone="info",
            ),
            p(
                "Si tu n'es pas à l'origine de cette demande, ignore cet "
                "email - ton mot de passe restera inchangé."
            ),
            closing(),
        ),
        "variables": ["prenom", "code", "ttl_minutes"],
    },
    # ────────────────────────────────────────────────────────────────────
    # AUDIT-A2 ajouts 2026-06-28 . 17 templates minimaux pour les events
    # qui n'avaient ni EventConfig ni EmailTemplate seede . silencieusement
    # perdus en prod.
    # ────────────────────────────────────────────────────────────────────
    # --- Reinscription annuelle D2 . phases urgent / today / suspended ---
    {
        "code": "member.reinscription_due_urgent",
        "objet": "Reinscription annuelle . plus que 7 jours",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton anniversaire d'adhesion arrive dans 7 jours"),
            lead(
                "Pour rester actif et continuer a beneficier de tous les services, "
                "renouvelle ton adhesion en reglant tes frais annuels."
            ),
            cta("Renouveler mon adhesion", "{portal_url}/renouvellement-adhesion"),
            p("Apres l'anniversaire, tu disposes d'un delai de grace avant suspension."),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "date_anniversaire", "lead_days", "grace_days", "portal_url"],
    },
    {
        "code": "member.reinscription_due_today",
        "objet": "Reinscription annuelle a faire aujourd'hui",
        "corps_html": _join(
            hi("{prenom}"),
            title("C'est aujourd'hui ton anniversaire d'adhesion"),
            lead(
                "Pour eviter une suspension de ton compte, renouvelle ton adhesion "
                "des aujourd'hui en reglant tes frais annuels."
            ),
            cta("Renouveler mon adhesion", "{portal_url}/renouvellement-adhesion"),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "date_anniversaire", "lead_days", "grace_days", "portal_url"],
    },
    {
        "code": "member.reinscription_expired_suspended",
        "objet": "Compte suspendu . non-renouvellement",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton compte a ete suspendu"),
            lead(
                "Faute de renouvellement dans le delai de grace, ton compte est passe "
                "en statut SUSPENDU. Tu peux le reactiver en reglant tes frais de "
                "renouvellement."
            ),
            cta("Reactiver mon compte", "{portal_url}/renouvellement-adhesion"),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "grace_days", "anchor", "portal_url"],
    },
    # --- BRC ---
    {
        "code": "member.brc_document_uploaded",
        "objet": "Justificatif BRC recu",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton justificatif BRC est bien recu"),
            lead("Notre equipe va l'examiner. Tu recevras une reponse rapidement."),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "nom_original"],
    },
    {
        "code": "member.brc_validated",
        "objet": "Statut BRC valide",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton statut BRC est confirme"),
            lead(
                "Ton justificatif a ete valide. Tu peux desormais beneficier des "
                "modalites credit reservees aux membres BRC."
            ),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "date_validation"],
    },
    {
        "code": "member.brc_rejected",
        "objet": "Justificatif BRC . a redeposer",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton justificatif BRC n'a pas pu etre valide"),
            callout("<strong>Motif :</strong> {motif}", tone="warn"),
            p("Tu peux redeposer un nouveau justificatif depuis ton espace."),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "motif"],
    },
    # --- Contentieux R1 (acte juridique) ---
    {
        "code": "loan.judicial_escalation_opened",
        "objet": "Escalade judiciaire ouverte . credit {loan_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton dossier de credit passe en procedure judiciaire"),
            lead(
                "Faute de regularisation, le dossier de credit <strong>{loan_dossier}</strong> "
                "est transmis a notre service juridique. Pour eviter toute aggravation, "
                "regularise au plus vite."
            ),
            closing(),
        ),
        "variables": ["prenom", "loan_dossier"],
    },
    {
        "code": "loan.biens_seized",
        "objet": "Saisie de biens engagee . credit {loan_dossier}",
        "corps_html": _join(
            hi("{prenom}"),
            title("Une procedure de saisie de biens est engagee"),
            lead(
                "Concernant ton credit <strong>{loan_dossier}</strong>, la procedure "
                "de saisie de biens corporels a ete declenchee. Notre equipe juridique "
                "te contactera pour les details."
            ),
            closing(),
        ),
        "variables": ["prenom", "loan_dossier"],
    },
    # --- Withdrawal ---
    {
        "code": "withdrawal.completed",
        "objet": "Retrait finalise",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton retrait a ete finalise"),
            lead(
                "Le montant de <strong>{montant} FCFA</strong> t'a ete remis "
                "({mode_paiement})."
            ),
            closing(),
        ),
        "variables": ["prenom", "numero_membre", "montant", "mode_paiement"],
    },
    # --- Lender (interets payes) ---
    {
        "code": "lender.interest_paid",
        "objet": "Interets de placement crediteurs",
        "corps_html": _join(
            hi("{prenom}"),
            title("Tes interets de placement sont credites"),
            lead(
                "Un versement d'interets de <strong>{montant} FCFA</strong> vient "
                "d'etre credite sur ton compte preteur."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant", "loan_dossier"],
    },
    {
        "code": "lender.interest_paid_at_source",
        "objet": "Interets de placement crediteurs (a la source)",
        "corps_html": _join(
            hi("{prenom}"),
            title("Tes interets de placement sont credites"),
            lead(
                "Une retenue d'interets a la source vient d'etre creditee sur ton "
                "compte preteur : <strong>{montant} FCFA</strong>."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant", "loan_dossier"],
    },
    # --- Microcampagne ---
    {
        "code": "microcampaign.closed",
        "objet": "Campagne {nom_campagne} cloturee",
        "corps_html": _join(
            hi("{prenom}"),
            title("La campagne {nom_campagne} est cloturee"),
            lead("Merci a tous ceux qui ont participe. Les dossiers retenus seront notifies separement."),
            closing(),
        ),
        "variables": ["prenom", "nom_campagne"],
    },
    # --- Epargne classique . maturite, renouvellement, archivage ---
    {
        "code": "savings.maturity_reached",
        "objet": "Ton epargne classique arrive a maturite",
        "corps_html": _join(
            hi("{prenom}"),
            title("Maturite de ton epargne classique"),
            lead(
                "Ton epargne classique a atteint sa date de maturite. Tu peux la "
                "renouveler pour un nouveau cycle, ou cloturer pour recuperer ton "
                "capital plus interets."
            ),
            cta("Gerer mon epargne", "{portal_url}/epargne"),
            closing(),
        ),
        "variables": ["prenom", "portal_url"],
    },
    {
        "code": "savings.renewed",
        "objet": "Epargne classique renouvelee",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton epargne classique est renouvelee"),
            lead("Un nouveau cycle d'epargne classique vient de demarrer."),
            closing(),
        ),
        "variables": ["prenom"],
    },
    {
        "code": "membership.archived_for_non_renewal",
        "objet": "Adhesion archivee . non-renouvellement",
        "corps_html": _join(
            hi("{prenom}"),
            title("Ton adhesion a ete archivee"),
            lead(
                "Faute de renouvellement de ton epargne classique a maturite, ton "
                "adhesion est passee en statut ARCHIVE. Contacte l'agence si tu "
                "souhaites reprendre."
            ),
            closing(),
        ),
        "variables": ["prenom"],
    },
    # --- Collecte fin de mois (bascule ou restitution) ---
    {
        "code": "collecte.balance_swept_to_savings",
        "objet": "Solde collecte bascule sur ton epargne",
        "corps_html": _join(
            hi("{prenom}"),
            title("Cloture mensuelle de ta collecte"),
            lead(
                "Conformement a ta preference, ton solde collecte de fin de mois "
                "(<strong>{montant} FCFA</strong>) a ete bascule sur ton epargne "
                "classique apres prelevement de la commission 1%."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant"],
    },
    {
        "code": "collecte.monthly_restitution",
        "objet": "Restitution de ta collecte mensuelle",
        "corps_html": _join(
            hi("{prenom}"),
            title("Restitution mensuelle de ta collecte"),
            lead(
                "Conformement a ta preference, le solde de ta collecte (<strong>"
                "{montant} FCFA</strong>) t'a ete restitue en especes apres "
                "prelevement de la commission 1%."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant"],
    },
    {
        "code": "placement.matured",
        "objet": "Ton placement est arrive a echeance",
        "corps_html": _join(
            hi("{prenom}"),
            title("Placement restitue"),
            lead(
                "Ton placement est arrive a sa date de restitution. Les interets "
                "(<strong>{interets} FCFA</strong>) ont ete credites sur ton "
                "epargne classique, et le capital est de nouveau librement "
                "retirable."
            ),
            closing(),
        ),
        "variables": ["prenom", "interets"],
    },
    {
        "code": "collecte.eom_choice_reminder",
        "objet": "Fin de mois : que faire de ta collecte ?",
        "corps_html": _join(
            hi("{prenom}"),
            title("La cloture mensuelle approche"),
            lead(
                "Ton solde de collecte est de <strong>{montant} FCFA</strong>. "
                "A la cloture, 1% est retenu par la cooperative. Tu peux choisir :"
            ),
            lead(
                "<strong>1. Retirer en cash</strong> a l'agence, ou "
                "<strong>2. Basculer vers ton epargne classique</strong>. "
                "Fais ton choix dans l'application (rubrique collecte) avant la "
                "cloture. Sans action, le retrait cash s'applique par defaut."
            ),
            closing(),
        ),
        "variables": ["prenom", "montant"],
    },
]


class Command(BaseCommand):
    help = (
        "Seed the transactional email templates used by the business hooks. "
        "Idempotent par défaut (skip si déjà en base) ; ``--force`` réécrit "
        "tous les templates listés (utilisé après refonte du design)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réécrit objet + corps_html + variables des templates existants.",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)
        created = 0
        updated = 0
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
            elif force:
                obj.objet = spec["objet"]
                obj.corps_html = spec["corps_html"]
                obj.variables = spec["variables"]
                obj.save(update_fields=["objet", "corps_html", "variables", "updated_at"])
                updated += 1
                self.stdout.write(self.style.WARNING(f"  ↻ {obj.code} (réécrit)"))
            else:
                existed += 1
                self.stdout.write(f"  · {obj.code} (déjà présent)")
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created} créé(s), {updated} réécrit(s), {existed} skipped."
            )
        )
