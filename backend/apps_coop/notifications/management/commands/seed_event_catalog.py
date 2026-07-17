"""Seed du catalogue d'événements métier (EXT-5).

Crée un ``EventConfig`` pour chacun des événements émis par l'application
(adhésion approuvée/rejetée, paiements, retards, retraits…), et pour
chacun un ``EventHook`` EMAIL pointant sur le template du même code.

Idempotent : ne touche jamais une ligne déjà éditée par l'admin
(statut, active, sensitive). Les nouveaux codes ajoutés au fil du temps
sont créés ; les codes déjà présents sont laissés tels quels.

**Sensitive par défaut** : les événements à valeur juridique ou opérationnelle
forte sont marqués ``sensitive=True``. L'admin reste libre de les couper
mais l'UI affichera une modale de confirmation (EXT-5c côté Next.js).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.notifications.models import EventConfig, EventHook


# (code, label, description, sensitive)
EVENTS: list[tuple[str, str, str, bool]] = [
    # --- Cycle de vie membre ---
    (
        "member.welcome",
        "Bienvenue (création de compte)",
        "Email envoyé juste après la création du compte membre.",
        False,
    ),
    (
        "member.activated",
        "Adhésion approuvée",
        "Article 1 - le membre est officiellement sociétaire après l'entretien d'admission.",
        True,
    ),
    (
        "member.rejected",
        "Adhésion rejetée",
        "Le candidat n'a pas été admis. Email avec motif.",
        True,
    ),
    (
        "membership.interview_scheduled",
        "Entretien d'admission enregistré",
        "Le comité a tenu l'entretien d'admission (Art. 3). Email d'information au candidat avec l'issue favorable / défavorable et l'avis.",
        True,
    ),
    (
        "campaign.created",
        "Nouvelle campagne micro-crédit",
        "Une nouvelle campagne micro-crédit a été lancée par la coopérative. Email + notification in-app diffusés à TOUS les membres ACTIF.",
        True,
    ),
    # --- Épargne ---
    (
        "savings.deposit_confirmed",
        "Versement d'épargne confirmé",
        "Reçu après crédit du versement (date de valeur appliquée).",
        False,
    ),
    (
        "savings.interest_credited",
        "Intérêts d'épargne crédités",
        "Cron mensuel - 1 % sur le solde collecté (Art. 4).",
        False,
    ),
    # --- Retraits ---
    (
        "withdrawal.requested",
        "Demande de retrait reçue",
        "Accusé de réception au membre.",
        False,
    ),
    (
        "withdrawal.approved",
        "Retrait approuvé",
        "Confirmation après débit atomique du solde.",
        True,
    ),
    (
        "withdrawal.rejected",
        "Retrait rejeté",
        "Email avec motif du rejet.",
        True,
    ),
    # --- Crédit : demande ---
    (
        "loan_request.submitted",
        "Demande de crédit déposée",
        "Accusé de réception après dépôt + frais payés.",
        False,
    ),
    (
        "loan_request.fees_paid",
        "Frais de demande crédit confirmés",
        "Le dossier passe en instruction.",
        False,
    ),
    (
        "loan_request.rejected",
        "Demande de crédit rejetée",
        "Décision du comité avec motif.",
        True,
    ),
    (
        "loan.approved",
        "Crédit approuvé par le comité",
        "Le membre doit accepter les conditions avant décaissement.",
        True,
    ),
    (
        "loan.disbursed",
        "Crédit décaissé",
        "Confirmation de virement Tara + récap échéancier.",
        True,
    ),
    # --- Crédit : remboursement / retards ---
    (
        "loan.repayment_confirmed",
        "Remboursement confirmé",
        "Reçu d'imputation FIFO sur les échéances.",
        False,
    ),
    (
        "loan.installment_due_soon",
        "Rappel J-N avant échéance",
        "Cron proactif - fenêtre J-N modifiable (EXT-1).",
        False,
    ),
    (
        "loan.installment_overdue",
        "Échéance en retard + pénalité",
        "Article 12 - la pénalité doit être notifiée pour être exigible.",
        True,
    ),
    (
        "loan.notice",
        "Mise en demeure",
        "Article 13 - acte juridique formel envoyé après plusieurs retards.",
        True,
    ),
    # --- Crédit : reconduction ---
    (
        "loan_renewal.requested",
        "Demande de reconduction reçue",
        "Accusé de réception.",
        False,
    ),
    (
        "loan_renewal.approved",
        "Reconduction approuvée",
        "Article 10/11 - +1 mois, taux comptant/reporté.",
        True,
    ),
    (
        "loan_renewal.rejected",
        "Reconduction rejetée",
        "Décision du comité avec motif.",
        True,
    ),
    # --- Carnet ---
    (
        "booklet.ordered",
        "Carnet commandé",
        "Confirmation de commande après paiement des 1 000 FCFA (Art. 4).",
        False,
    ),
    # --- Réinscription annuelle (A2) ---
    (
        "member.reinscription_due",
        "Rappel de réinscription annuelle (alerte douce)",
        "A2 - Émis J-N avant l'anniversaire annuel d'adhésion. Non bloquant.",
        False,
    ),
    (
        "member.reinscription_confirmed",
        "Réinscription annuelle confirmée",
        "L'admin a acté la re-souscription : la prochaine échéance est décalée de 12 mois.",
        False,
    ),
    # --- Cycle contentieux (R1) ---
    (
        "loan.penalite_globale_appliquee",
        "Pénalité globale (50 % × solde) appliquée",
        "Date limite globale du crédit franchie sans solde nul - pénalité "
        "ajoutée. Le membre a un délai de grâce avant la saisie de l'épargne.",
        True,
    ),
    (
        "loan.savings_seized",
        "Épargne saisie automatiquement (R1)",
        "Le cron de contentieux a prélevé sur l'épargne du membre pour solder "
        "le crédit. Acte à valeur juridique : la notification est obligatoire.",
        True,
    ),
    (
        "loan.poursuite_engaged",
        "Poursuites judiciaires engagées",
        "L'épargne n'a pas couvert l'intégralité du crédit après saisie : "
        "le dossier passe au recouvrement contentieux (huissier/avocat).",
        True,
    ),
    # --- LOT 10 : Avaliste (caution) flow §7.2 ---
    (
        "loan.avaliste_consent_requested",
        "Désignation comme avaliste - demande de consentement",
        "Un membre a désigné un autre membre comme avaliste. L'avaliste doit "
        "accepter ou refuser dans son espace. Mail à l'avaliste désigné.",
        True,
    ),
    (
        "loan.avaliste_consent_accepted",
        "Avaliste a accepté la caution",
        "L'avaliste désigné a confirmé son engagement. La demande passe en "
        "instruction comité. Mail au demandeur de crédit.",
        False,
    ),
    (
        "loan.avaliste_consent_refused",
        "Avaliste a refusé la caution",
        "L'avaliste désigné a refusé de se porter caution. Le demandeur peut "
        "désigner un autre avaliste. Mail au demandeur de crédit.",
        True,
    ),
    # --- LOT 8 : Funding prêteur 24h §6 ---
    (
        "loan.funding.consent_requested",
        "Demande de funding à un prêteur (24h)",
        "Une partie du crédit est proposée à un prêteur (membre avec consent "
        "épargne-prêteur). Sans réponse en 24h, auto-acceptation. Mail au prêteur.",
        True,
    ),
    (
        "loan.funding.completed",
        "Funding complet - crédit prêt au décaissement",
        "L'ensemble des tranches du crédit est sécurisé. Mail au demandeur "
        "avec annonce du décaissement imminent.",
        False,
    ),
    (
        "loan.funding.exhausted",
        "Funding épuisé - intervention admin requise",
        "Après plusieurs vagues de sollicitation, le crédit ne peut être "
        "couvert intégralement par l'épargne-prêteur. Mail au demandeur ; "
        "le dossier attend une décision admin.",
        True,
    ),
    # A5 . Engagement manuel d'une tranche preteur par l'admin (composer
    # funding). Mail + notif in-app au preteur AVANT que les interets ne
    # commencent a courir sur sa portion engagee.
    (
        "lender.tranche_engaged",
        "Votre placement vient d'être engagé dans un crédit",
        "L'administration a engagé une partie de votre épargne placement pour "
        "financer un crédit. Les intérêts commencent à courir aujourd'hui sur "
        "cette portion. Mail + notif in-app au prêteur, au moment exact de "
        "l'engagement.",
        True,
    ),
    # --- AUDIT-A2 ajouts 2026-06-28 . events emis dans le code mais sans
    # EventConfig . silencieusement perdus en prod (ni email ni notif).
    # ---------------------------------------------------------------------
    # Réinscription annuelle D2 . phases urgent / today / suspended.
    (
        "member.reinscription_due_urgent",
        "Rappel urgent de réinscription (J-7)",
        "D2 . Émis 7 jours avant l'anniversaire annuel d'adhésion.",
        True,
    ),
    (
        "member.reinscription_due_today",
        "Anniversaire de réinscription atteint (J0)",
        "D2 . Émis le jour-meme de l'anniversaire annuel.",
        True,
    ),
    (
        "member.reinscription_expired_suspended",
        "Compte suspendu pour non-renouvellement",
        "D2 . Emis quand la fenetre de grace (J+30) est depassee . le membre "
        "passe en SUSPENDU. Email obligatoire (acte juridique).",
        True,
    ),
    # BRC . cycle complet (upload / validation / rejet)
    (
        "member.brc_document_uploaded",
        "Justificatif BRC reçu",
        "LOT 1 . Le membre a uploadé un nouveau justificatif BRC. Accusé de réception.",
        False,
    ),
    (
        "member.brc_validated",
        "Statut BRC validé",
        "LOT 1 . L'admin a valide le justificatif . le membre devient is_brc_member=True.",
        False,
    ),
    (
        "member.brc_rejected",
        "Justificatif BRC rejeté",
        "LOT 1 . L'admin a rejete le justificatif avec un motif . le membre peut re-uploader.",
        True,
    ),
    # Contentieux R1 . escalade judiciaire et saisie biens
    (
        "loan.judicial_escalation_opened",
        "Escalade judiciaire ouverte",
        "LOT 14 . Acte juridique formel . le dossier passe en phase D (huissier). "
        "Notification au membre.",
        True,
    ),
    (
        "loan.biens_seized",
        "Saisie de biens engagée",
        "LOT 14 . Phase E . la procedure de saisie de biens corporels est engagee.",
        True,
    ),
    # Withdrawal . confirmation finale (acte juridique cote tresorerie)
    (
        "withdrawal.completed",
        "Retrait livré",
        "W3 . Confirmation finale apres remise des especes (presentiel) ou payout "
        "Tara reussi. Cloture du dossier de retrait.",
        True,
    ),
    # Lender . versement d'interets aux preteurs (T0 source CH-12 + maturite)
    (
        "lender.interest_paid",
        "Intérêts placement crédités",
        "Versement d'interets sur le placement preteur (cycle paiement classique).",
        False,
    ),
    (
        "lender.interest_paid_at_source",
        "Intérêts placement crédités à la source",
        "CH-12 . Distribution immediate des interets a T0 du decaissement.",
        False,
    ),
    # Microcampagne . cloture
    (
        "microcampaign.closed",
        "Microcampagne clôturée",
        "LOT 11 . La campagne micro-credit est fermee (deadline atteinte ou volonte admin).",
        False,
    ),
    # Epargne classique . maturite, renouvellement, archivage
    (
        "savings.maturity_reached",
        "Maturité d'épargne classique atteinte",
        "LOT 5 . Une epargne classique a atteint sa date de prochaine_maturite . "
        "le membre doit decider renouveler ou cloturer.",
        True,
    ),
    (
        "savings.renewed",
        "Épargne classique renouvelée",
        "L'epargne classique a ete renouvelee pour un nouveau cycle.",
        False,
    ),
    (
        "membership.archived_for_non_renewal",
        "Adhésion archivée (non-renouvellement épargne)",
        "L'epargne classique a expire sans renouvellement . le compte est archive.",
        True,
    ),
    # Collecte . cloture mensuelle (commission 1% + restitution)
    (
        "collecte.balance_swept_to_savings",
        "Solde collecte basculé sur épargne",
        "LOT 4 . Fin de mois . le solde collecte du membre est bascule vers son "
        "epargne classique (apres prelevement de la commission 1%).",
        False,
    ),
    (
        "collecte.monthly_restitution",
        "Restitution collecte fin de mois",
        "LOT 4 . Fin de mois . versement en cash de la collecte du membre (apres "
        "prelevement de la commission 1%).",
        False,
    ),
    (
        "collecte.eom_choice_reminder",
        "Rappel choix fin de mois collecte",
        "Fin de mois 2026 . Rappel envoye avant la cloture : le membre choisit "
        "de recuperer sa collecte en cash ou de la basculer vers son epargne. "
        "Template editable par l'admin.",
        False,
    ),
    (
        "placement.matured",
        "Placement arrivé à échéance",
        "Placement 2026 . A la date de restitution (defaut 1er janvier), le "
        "placement DISPONIBLE du membre est restitue avec ses interets prorata "
        "et redevient librement retirable.",
        False,
    ),
]


class Command(BaseCommand):
    help = (
        "Seed le catalogue EventConfig + EventHook (1 hook EMAIL par "
        "événement, ciblant le template du même code). Idempotent."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created_cfg = 0
        created_hook = 0
        for code, label, description, sensitive in EVENTS:
            cfg, was_created = EventConfig.objects.get_or_create(
                code=code,
                defaults={
                    "label": label,
                    "description": description,
                    "status": EventConfig.Status.OPTIONAL,
                    "active": True,
                    "sensitive": sensitive,
                },
            )
            if was_created:
                created_cfg += 1
                flag = " [SENSITIVE]" if sensitive else ""
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Event   {code:<35} {label}{flag}")
                )
            else:
                self.stdout.write(
                    f"  · Event   {code} (déjà en base - non modifié)"
                )

            # Hook EMAIL par défaut : on cible le template du même code.
            hook, hook_was_created = EventHook.objects.get_or_create(
                event=cfg,
                action_type=EventHook.ActionType.EMAIL,
                defaults={
                    "target_template_code": "",  # vide → fallback sur event.code
                    "active": True,
                    "ordering": 100,
                },
            )
            if hook_was_created:
                created_hook += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{created_cfg} événement(s) créé(s), "
                f"{created_hook} hook(s) EMAIL créé(s)."
            )
        )
