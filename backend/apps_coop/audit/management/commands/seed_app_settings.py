"""Seed des AppSetting tunables (EXT-1).

Catalogue des **scalaires entiers et chaînes** que l'admin peut ajuster sans
déploiement (seuils, délais, lieu d'agence, etc.). Idempotent : crée les clés
manquantes à leur valeur réglementaire et ne touche JAMAIS une ligne déjà
éditée par l'admin.

Les valeurs par défaut listées ici miroitent les défauts réglementaires
codés dans ``loans/terms.py``, ``loans/tasks.py`` et ``savings/cutoff.py``.
Aucun calcul ne plante si la table n'est pas seedée — les services tombent
sur ces mêmes défauts via ``get_int_setting()`` / ``get_str_setting()``.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.audit.models import AppSetting


SETTINGS: list[tuple[str, str, str]] = [
    # (clé, valeur par défaut, description)
    (
        "loans.contentieux.threshold_days",
        "90",
        "Article 13 — au-delà de ce nombre de jours de retard sur une "
        "échéance, le crédit bascule en CONTENTIEUX.",
    ),
    (
        "loans.due_soon.lead_days",
        "3",
        "Délai (jours) du rappel proactif J-3 avant échéance.",
    ),
    (
        "loans.renewal.extra_months",
        "1",
        "Article 10 — prorogation fixe accordée à la reconduction (+ N mois).",
    ),
    (
        "savings.cutoff.hour",
        "17",
        "Article 4 — heure de cut-off (Africa/Douala). Un dépôt après cette "
        "heure est posté à J+1 ouvré.",
    ),
    (
        "savings.collection_location",
        "GATHE FINANCE — Akwa Douala Bercy",
        "Libellé du lieu d'agence (canal de secours, l'app étant le canal principal).",
    ),
    (
        "members.reinscription.lead_days",
        "30",
        "A2 — Nombre de jours avant l'anniversaire annuel pour envoyer "
        "le rappel de réinscription (alerte douce, non bloquante).",
    ),
    (
        "members.reinscription.grace_days",
        "10",
        "G5 (2026-07) — Délai (jours) après la clôture du cycle avant le "
        "passage automatique INACTIF/SUSPENDU. Défaut 10. La réactivation "
        "exige le re-paiement des frais d'adhésion + inscription.",
    ),
    (
        "loans.penalite_globale.grace_days",
        "30",
        "Cycle contentieux — délai (jours) entre l'application de la "
        "pénalité globale (50 % × solde) et le passage en CONTENTIEUX qui "
        "déclenche la saisie automatique sur l'épargne.",
    ),
    (
        "loans.penalite_par_echeance.enabled",
        "false",
        "Active (true/false) la pénalité Art.12 PAR ÉCHÉANCE manquée "
        "(en plus de marquer EN_RETARD). Par défaut FALSE : la pénalité "
        "ne s'applique qu'au franchissement de la date limite globale "
        "(50 % × solde restant, règle 2026).",
    ),
    # LOT 1 — Refonte 2026 — Identifiant membre + ancienneté.
    (
        "member.id.format",
        "GF-{year}-{seq:04d}",
        "Format du numéro d'identification membre (numero_membre). "
        "Placeholders supportés : {year} (année courante) et {seq} "
        "(séquence annuelle, padding via {seq:04d} pour 4 chiffres). "
        "Défaut : GF-{year}-{seq:04d} → ex. GF-2026-0001.",
    ),
    (
        "seniority.threshold_months",
        "12",
        "Ancienneté minimale (en mois) pour être considéré comme 'Ancien' "
        "(§3 BUSINESS_RULES_2026). Débloque la voie d'éligibilité crédit "
        "direct (avec validation BRC) et le rôle d'avaliste pour un "
        "nouvel adhérent.",
    ),
    # LOT 2 — Refonte 2026 — Collecte journalière + Épargne classique.
    (
        "collecte.min_per_day",
        "1000",
        "Montant minimum par jour pour la collecte journalière "
        "(§4 BUSINESS_RULES_2026). Le membre peut verser plus mais "
        "le multi-jours pré-payé est un multiple de cette valeur.",
    ),
    (
        "collecte.prepay.max_days",
        "30",
        "Nombre maximum de jours pré-payables en un seul versement "
        "(§4 BUSINESS_RULES_2026). Plafond UI pour le mode multi-jours.",
    ),
    (
        "collecte.monthly.default_action",
        "cash",
        "Comportement par défaut en fin de mois pour les comptes "
        "collecte : 'cash' (retrait espèces) ou 'epargne' (bascule "
        "vers épargne classique). Le membre peut le surcharger par compte.",
    ),
    (
        "epargne.contract_months",
        "12",
        "Durée du contrat d'épargne classique en mois (§5 BUSINESS_RULES_2026). "
        "À l'échéance : restitution intégrale + frais de ré-inscription.",
    ),
    (
        "epargne.renewal_fee",
        "5000",
        "Frais de ré-inscription annuel pour renouveler le contrat "
        "d'épargne classique (FCFA). Au-delà du grace, le compte est archivé.",
    ),
    (
        "epargne.renewal_grace_days",
        "30",
        "Délai de grâce (en jours) après la date de maturité pour payer "
        "les frais de ré-inscription. Dépassement → statut ARCHIVE.",
    ),
    # CH-11 — Retenue des intérêts à la source au décaissement.
    (
        "loans.interest_withheld_at_source",
        "true",
        "Quand 'true' (par défaut) la coop retient 10 % d'intérêts à la "
        "mise à disposition : le membre reçoit 90 % du montant nominal et "
        "rembourse uniquement ce qu'il a touché. 'false' restaure le mode "
        "historique (capital + intérêts répartis sur les échéances). "
        "S'applique aux nouveaux crédits seulement — les crédits déjà "
        "approuvés conservent leur mode figé à l'approbation.",
    ),
    # CH-7 — Frais d'étude du dossier crédit (non-remboursables).
    (
        "loans.study_fee.non_refundable_notice",
        "Ces frais d'étude couvrent l'instruction du dossier et la visite "
        "terrain éventuelle. Ils sont non-remboursables, y compris en cas "
        "de refus de la demande.",
        "Mention affichée sur le portail au moment du paiement des frais "
        "d'étude du dossier crédit. Modifie ce texte pour ajuster la formulation "
        "(la non-restitution est définitive dans tous les cas).",
    ),
    # CH-3 — Épargne classique : sous-canal placement.
    # Le placement réutilise la convention prêteur (LOT 7) — chaque dépôt
    # placement crée automatiquement une LenderTranche disponible. Le partage
    # des intérêts crédit utilise `lender.interest_share_rate` (LOT 9), déjà
    # configurable plus bas. Un seul flag dédié ici : kill-switch global.
    (
        "epargne.placement.enabled",
        "true",
        "Ouvre/ferme le sous-canal placement de l'épargne classique. "
        "Si 'false' : la case 'placer ce dépôt' est masquée côté portail "
        "et les dépôts ne créent plus de LenderTranche.",
    ),
    # Placement — restitution à échéance (refonte 2026-07). Date fixe éditable.
    (
        "epargne.placement.maturity.enabled",
        "true",
        "Active la restitution automatique des placements à échéance "
        "(cron placement.maturity.daily). Si 'false', aucune restitution auto.",
    ),
    (
        "epargne.placement.maturity_date",
        "01-01",
        "Date annuelle (format MM-DD) de restitution des placements avec "
        "intérêts. Défaut 01-01 (1er janvier). Éditable.",
    ),
    (
        "epargne.placement.interest_rate",
        "0.01",
        "Taux MENSUEL du placement (ex. '0.01' = 1%/mois). L'intérêt versé à "
        "l'échéance = taux × montant × (jours depuis le dépôt / 30).",
    ),
    # Rappel mensuel du choix de fin de mois collecte (cash vs bascule épargne).
    (
        "collecte.eom_reminder.enabled",
        "true",
        "Active la notification mensuelle (cron le 25) qui invite les membres "
        "à choisir cash vs bascule épargne avant la clôture de la collecte.",
    ),
    # LOT 3 — Kill-switch pour la logique 2025 obsolète.
    (
        "savings.monthly_interest.enabled",
        "false",
        "LEGACY — Active (true/false) le crédit 1%/mois sur les comptes "
        "de collecte journalière (intérêt épargne 2025). Par défaut FALSE "
        "en refonte 2026 : le cron tourne à blanc en attendant que le LOT 4 "
        "livre la nouvelle logique (commission 1% prélevée + restitution).",
    ),
    # LOT 4 — Cron mensuel de clôture des collectes (refonte 2026).
    (
        "collecte.monthly.enabled",
        "true",
        "Active (true/false) le cron mensuel de clôture des comptes de "
        "collecte journalière (§4 BUSINESS_RULES_2026). Par défaut TRUE.",
    ),
    (
        "collecte.monthly.commission_rate",
        "0.01",
        "Taux de commission prélevée par la coopérative à la clôture "
        "mensuelle d'un compte de collecte journalière (§4 BUSINESS_RULES_2026). "
        "Défaut 0.01 = 1 % du solde. L'admin peut ajuster (0 = restitution "
        "intégrale, 0.02 = 2 %, etc.) depuis la page Paramètres 2026.",
    ),
    # LOT 7 — Convention prêteur / épargne-prêteur (§6 BUSINESS_RULES_2026).
    (
        "lender.tranche.min_amount",
        "5000",
        "Montant minimum d'une tranche prêteur en XAF (mode B). "
        "Par défaut 5 000 XAF — évite les micro-tranches difficiles à allouer.",
    ),
    (
        "lender.consent.min_seniority_months",
        "0",
        "Ancienneté minimale (mois) pour pouvoir signer la convention "
        "prêteur. Par défaut 0 = pas de minimum. Mettre 12 pour réserver "
        "le rôle aux 'Anciens'.",
    ),
    # LOT 8 — Funding state machine (§7.3 BUSINESS_RULES_2026).
    (
        "funding.window_hours",
        "24",
        "Fenêtre d'acceptation tacite d'une LenderConsentRequest. Au-delà "
        "le cron pose AUTO_ACCEPTED. Par défaut 24h.",
    ),
    (
        "funding.allocation_strategy",
        "first_fit",
        "Stratégie d'allocation funding : 'first_fit' (gros prêteurs d'abord, "
        "moins de prêteurs sollicités) ou 'balanced' (réparti équitablement, "
        "risque mutualisé).",
    ),
    # LOT 9 — Partage 50/50 des intérêts crédit (§7.5 BUSINESS_RULES_2026).
    (
        "lender.interest_share_rate",
        "0.5",
        "Fraction des intérêts crédit reversée aux prêteurs à chaque "
        "imputation (le complément reste à la coop). Décimal entre 0 et 1, "
        "défaut 0.5 (50/50). Mettre 0 désactive le partage (legacy 2025).",
    ),
    # LOT 10 — Voie 2 AVALISTE (§7.2 BUSINESS_RULES_2026).
    (
        "loans.avaliste.min_coverage_ratio",
        "1.00",
        "Couverture minimale (épargne_demandeur + épargne_avaliste) / "
        "montant_demande. Défaut 1.00 = 100 %. À durcir (1.20 etc.) pour "
        "renforcer la garantie morale.",
    ),
    (
        "loans.avaliste.allow_multiple",
        "false",
        "Autorise plusieurs avalistes pour un même crédit (true/false). "
        "Par défaut FALSE — règle 2026 = 1 avaliste = 1 crédit.",
    ),
    # LOT 11 — Voie 3 MICROCAMPAIGN (§8 BUSINESS_RULES_2026).
    (
        "loans.campaign.default_montant_min",
        "5000",
        "Plancher par défaut du montant d'un micro-crédit campagne (FCFA). "
        "Utilisé par l'UI admin pour pré-remplir le formulaire ; chaque "
        "campagne peut surcharger via ``MicrocreditCampaign.montant_min``.",
    ),
    (
        "loans.campaign.default_montant_max",
        "50000",
        "Plafond par défaut du montant d'un micro-crédit campagne (FCFA). "
        "Surchargé par campagne. 50 000 est le ceiling guideline §8.",
    ),
    (
        "loans.campaign.default_taux",
        "0.10",
        "Taux d'intérêt flat par défaut sur un micro-crédit campagne. "
        "Standard règlement = 10 %.",
    ),
    (
        "loans.campaign.default_recovery_days",
        "60",
        "Durée par défaut du recouvrement (jours) — collectes journalières "
        "dédiées sur la dette campagne.",
    ),
    # LOT 12 — Routeur d'éligibilité 3 voies (§7.1 BUSINESS_RULES_2026).
    # Ces toggles donnent à l'admin un libre arbitre total : il peut
    # désactiver une voie sans déploiement (kill-switch) ou réorganiser
    # leur priorité d'évaluation.
    (
        "loans.eligibility.allow_senior_brc",
        "true",
        "Active (true/false) la voie SENIOR_BRC. Mettre 'false' pour bloquer "
        "temporairement les demandes directes des Anciens BRC (ex. moratoire).",
    ),
    (
        "loans.eligibility.allow_avaliste",
        "true",
        "Active (true/false) la voie AVALISTE pour les nouveaux adhérents. "
        "Mettre 'false' pour désactiver le rôle de garant.",
    ),
    (
        "loans.eligibility.allow_campaign",
        "true",
        "Active (true/false) la voie MICROCAMPAIGN. Mettre 'false' pour "
        "bloquer toutes les demandes campagne sans toucher au modèle.",
    ),
    (
        "loans.eligibility.require_brc_for_senior",
        "true",
        "Si 'true' (défaut), un Ancien doit avoir le statut BRC validé pour "
        "passer Voie 1. Si 'false', l'ancienneté seule suffit (cas où l'admin "
        "veut temporairement contourner la validation BRC).",
    ),
    (
        "loans.eligibility.route_priority",
        "senior_brc,avaliste,campaign",
        "Ordre d'évaluation des 3 voies (CSV). Première qui matche gagne. "
        "Une voie absente est désactivée. Permet à l'admin de promouvoir "
        "une voie (ex. campagne en avant : 'campaign,senior_brc,avaliste').",
    ),
    # LOT 13 — Saisie multi-source R1 (§9.2 BUSINESS_RULES_2026).
    (
        "loans.seizure.source_order",
        "borrower_classique,borrower_collecte,avaliste_classique,avaliste_collecte",
        "Ordre des sources balayées à la saisie d'un crédit en contentieux "
        "(CSV). Une source absente = ignorée. Admin peut adoucir l'impact "
        "borrower (ex. 'avaliste_collecte,borrower_collecte') ou désactiver "
        "la saisie classique en l'omettant.",
    ),
    (
        "loans.seizure.include_avaliste",
        "true",
        "Active (true/false) la saisie sur l'épargne de l'avaliste si "
        "``LoanRequest.avaliste`` est posé. False = saisie strictement "
        "limitée aux comptes du débiteur (rare, mais possible).",
    ),
    (
        "loans.seizure.exclude_engaged_tranches",
        "true",
        "Q5 — exclut le montant des ``LenderTranche.ENGAGEE`` du solde "
        "saisissable sur l'épargne classique. À NE PAS désactiver sauf "
        "audit forensique.",
    ),
    # LOT 14 — Escalade judiciaire phase D/E (§9.3 BUSINESS_RULES_2026).
    (
        "loans.judicial_escalation.mode",
        "manual",
        "Mode de déclenchement de l'escalade judiciaire après échec saisie "
        "épargne. 'manual' (défaut, admin clique), 'auto' (cron pose après "
        "delay_days), 'hybrid' (notif J-N puis pose à J0).",
    ),
    (
        "loans.judicial_escalation.delay_days",
        "60",
        "Nombre de jours entre 'poursuite_judiciaire_at' (échec R1) et le "
        "déclenchement d'une escalade auto (mode 'auto'/'hybrid' uniquement).",
    ),
    (
        "loans.judicial_escalation.notify_before_days",
        "7",
        "Préavis (jours) avant déclenchement auto en mode 'hybrid' — délai "
        "laissé à l'admin pour intervenir avant l'escalade automatique.",
    ),
    # CH-2 (chantier juin 2026) — Activation membre conditionnée au paiement
    # complet des 3 frais (adhésion + inscription + carnet).
    (
        "membership.payment_deadline_days",
        "30",
        "CH-2 — Délai max (jours) après approbation de la demande d'adhésion "
        "pour régler les 3 frais (adhésion + inscription + carnet). Au-delà, "
        "le dossier peut être marqué expiré par l'admin (action manuelle pour "
        "l'instant). Le membre reste suspendu tant que les 13 000 FCFA ne "
        "sont pas tous payés.",
    ),
]


class Command(BaseCommand):
    help = (
        "Seed les AppSetting tunables (seuils, délais, cut-off, lieu). "
        "Idempotent : ne réécrit jamais une valeur déjà éditée par l'admin."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        kept = 0
        for cle, valeur, description in SETTINGS:
            obj, was_created = AppSetting.objects.get_or_create(
                cle=cle,
                defaults={"valeur": valeur, "description": description},
            )
            if was_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created  {cle:<40} = {valeur}")
                )
            else:
                kept += 1
                self.stdout.write(
                    f"  · Kept     {cle:<40} = {obj.valeur} (admin-edited)"
                )
        self.stdout.write(
            self.style.SUCCESS(f"\n{created} créé(s), {kept} déjà en base.")
        )
