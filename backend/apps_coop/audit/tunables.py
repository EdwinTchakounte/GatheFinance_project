"""Catalogue des AppSettings admin-éditables (refonte 2026 P2).

Source de vérité unique pour l'UI admin de configuration runtime. Chaque
entrée déclare :

  - ``key``          : la clé AppSetting (str).
  - ``group``        : regroupement UI (member, collecte, epargne, lender,
                       funding, eligibility, seizure, judicial, campaign,
                       loans, savings, members).
  - ``label``        : intitulé court (FR) affiché dans le formulaire.
  - ``description``  : explication métier (1-3 phrases).
  - ``type``         : ``int`` / ``decimal`` / ``bool`` / ``str`` / ``csv`` /
                       ``enum`` — pilote le widget UI et la validation.
  - ``default``      : valeur par défaut (str — stockée brute dans AppSetting).
  - ``choices`` (opt) : pour le type ``enum``, liste des valeurs autorisées.
  - ``min`` / ``max`` (opt) : pour ``int`` / ``decimal``.

⚠ Ne pas confondre avec ``FeeType`` (frais en FCFA) et ``RateParam`` (taux
crédit) : ceux-là vivent dans ``payments`` et sont édités via
``/payments/admin/config/`` (BR2/BR3). Ici on ne touche QU'AUX AppSettings.
"""
from __future__ import annotations

from typing import Optional


# Groupes UI — ordre d'affichage des sections (le frontend les rend dans cet ordre).
GROUPS_ORDER = [
    ("member", "Membre"),
    ("seniority", "Ancienneté"),
    ("collecte", "Collecte journalière"),
    ("epargne", "Épargne classique"),
    ("savings", "Épargne (legacy)"),
    ("members", "Réinscription"),
    ("loans", "Crédit (général)"),
    ("lender", "Épargne-prêteur"),
    ("funding", "Funding crédit"),
    ("eligibility", "Éligibilité (3 voies)"),
    ("avaliste", "Avaliste"),
    ("campaign", "Micro-campagne"),
    ("seizure", "Saisie épargne"),
    ("judicial", "Escalade judiciaire"),
]


CATALOG: list[dict] = [
    # LOT 1 — Identifiant membre + ancienneté
    {
        "key": "member.id.format",
        "group": "member",
        "label": "Format du numéro membre",
        "description": "Patron Python pour générer numero_membre. Placeholders {year} et {seq}.",
        "type": "str",
        "default": "GF-{year}-{seq:04d}",
    },
    {
        "key": "seniority.threshold_months",
        "group": "seniority",
        "label": "Ancienneté minimum (mois)",
        "description": "Ancienneté (en mois) à partir de laquelle un membre est considéré comme « Ancien » : ouvre la voie de crédit réservée aux membres établis et le rôle de garant.",
        "type": "int",
        "default": "12",
        "min": 0,
        "max": 120,
    },
    # LOT 2 — Collecte journalière + épargne classique
    {
        "key": "collecte.min_per_day",
        "group": "collecte",
        "label": "Montant minimum journalier (FCFA)",
        "description": "Plancher journalier. Le membre peut verser plus, multi-jours = multiple.",
        "type": "int",
        "default": "1000",
        "min": 0,
    },
    {
        "key": "collecte.prepay.max_days",
        "group": "collecte",
        "label": "Pré-paiement max (jours)",
        "description": "Nombre max de jours pré-payables en un versement (UI multi-jours).",
        "type": "int",
        "default": "30",
        "min": 1,
        "max": 365,
    },
    {
        "key": "collecte.monthly.default_action",
        "group": "collecte",
        "label": "Action fin de mois (défaut)",
        "description": "Comportement par défaut à la clôture : 'cash' (retrait) ou 'epargne' (bascule classique).",
        "type": "enum",
        "default": "cash",
        "choices": ["cash", "epargne"],
    },
    {
        "key": "epargne.contract_months",
        "group": "epargne",
        "label": "Durée du contrat (mois)",
        "description": "Durée du contrat d'épargne classique avant restitution intégrale et frais de renouvellement.",
        "type": "int",
        "default": "12",
        "min": 1,
        "max": 60,
    },
    {
        "key": "epargne.renewal_fee",
        "group": "epargne",
        "label": "Frais de ré-inscription (FCFA)",
        "description": "Montant exigé à la maturité 12 mois pour renouveler le contrat épargne classique.",
        "type": "int",
        "default": "5000",
        "min": 0,
    },
    {
        "key": "epargne.renewal_grace_days",
        "group": "epargne",
        "label": "Délai de grâce ré-inscription (jours)",
        "description": "Délai après maturité pour payer les frais avant archivage du compte.",
        "type": "int",
        "default": "30",
        "min": 0,
        "max": 90,
    },
    # LOT 3 — Kill-switch legacy
    {
        "key": "savings.monthly_interest.enabled",
        "group": "savings",
        "label": "Intérêt collecte 1%/mois (dispositif hérité)",
        "description": "Dispositif hérité : active le crédit d'intérêts mensuels sur la collecte. Désactivé par défaut.",
        "type": "bool",
        "default": "false",
    },
    # LOT 4 — Cron clôture mensuelle
    {
        "key": "collecte.monthly.enabled",
        "group": "collecte",
        "label": "Cron clôture mensuelle activé",
        "description": "Active ou non la clôture mensuelle automatique des comptes de collecte (commission + restitution ou bascule).",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "collecte.monthly.commission_rate",
        "group": "collecte",
        "label": "Commission fin de mois (ratio)",
        "description": (
            "Taux prélevé à la clôture mensuelle d'un compte de collecte "
            "journalière. Défaut 0.01 = 1 %. "
            "Mettre 0 pour une restitution intégrale, 0.02 pour 2 %, etc."
        ),
        "type": "decimal",
        "default": "0.01",
        "min": 0,
        "max": 1,
    },
    # Crédit + cycle contentieux
    {
        "key": "loans.contentieux.threshold_days",
        "group": "loans",
        "label": "Seuil retard → contentieux (jours)",
        "description": "Article 13 — au-delà, l'échéance bascule en CONTENTIEUX.",
        "type": "int",
        "default": "90",
        "min": 0,
    },
    {
        "key": "loans.due_soon.lead_days",
        "group": "loans",
        "label": "Préavis échéance (jours)",
        "description": "Délai du rappel proactif J-N avant échéance.",
        "type": "int",
        "default": "3",
        "min": 0,
        "max": 30,
    },
    {
        "key": "loans.renewal.extra_months",
        "group": "loans",
        "label": "Prorogation reconduction (+N mois)",
        "description": "Article 10 — prorogation fixe accordée à la reconduction.",
        "type": "int",
        "default": "1",
        "min": 1,
        "max": 12,
    },
    {
        "key": "loans.penalite_globale.grace_days",
        "group": "loans",
        "label": "Grâce pénalité globale (jours)",
        "description": "Délai entre la pénalité 50 % et le passage CONTENTIEUX (saisie auto).",
        "type": "int",
        "default": "30",
        "min": 0,
    },
    {
        "key": "loans.penalite_par_echeance.enabled",
        "group": "loans",
        "label": "Pénalité par échéance (Art.12)",
        "description": "Active la pénalité PAR échéance manquée. FALSE par défaut en 2026 (uniquement globale).",
        "type": "bool",
        "default": "false",
    },
    # Cut-off + lieu
    {
        "key": "savings.cutoff.hour",
        "group": "savings",
        "label": "Heure cut-off (Africa/Douala)",
        "description": "Article 4 — un dépôt après cette heure est posté à J+1 ouvré.",
        "type": "int",
        "default": "17",
        "min": 0,
        "max": 23,
    },
    {
        "key": "savings.collection_location",
        "group": "savings",
        "label": "Lieu de collecte (libellé)",
        "description": "Affiché en canal de secours quand le membre vient à l'agence.",
        "type": "str",
        "default": "GATHE FINANCE — Akwa Douala Bercy",
    },
    {
        "key": "members.reinscription.lead_days",
        "group": "members",
        "label": "Préavis réinscription (jours)",
        "description": "Délai du rappel envoyé au membre avant son anniversaire annuel d'adhésion.",
        "type": "int",
        "default": "30",
        "min": 0,
    },
    # LOT 7 — Lender
    {
        "key": "lender.tranche.min_amount",
        "group": "lender",
        "label": "Tranche prêteur min. (FCFA)",
        "description": "Montant minimum d'une tranche prêteur. Évite les très petits montants.",
        "type": "int",
        "default": "5000",
        "min": 0,
    },
    {
        "key": "lender.consent.min_seniority_months",
        "group": "lender",
        "label": "Ancienneté min. prêteur (mois)",
        "description": "Ancienneté minimale pour signer la convention prêteur. 0 = pas de minimum.",
        "type": "int",
        "default": "0",
        "min": 0,
    },
    # LOT 8 — Funding
    {
        "key": "funding.window_hours",
        "group": "funding",
        "label": "Fenêtre acceptation (heures)",
        "description": "Délai laissé à un prêteur pour accepter de financer un crédit ; au-delà, l'acceptation est appliquée automatiquement.",
        "type": "int",
        "default": "24",
        "min": 1,
        "max": 168,
    },
    {
        "key": "funding.allocation_strategy",
        "group": "funding",
        "label": "Stratégie d'allocation",
        "description": "first_fit (gros prêteurs d'abord) ou balanced (réparti équitable).",
        "type": "enum",
        "default": "first_fit",
        "choices": ["first_fit", "balanced"],
    },
    # LOT 9 — Split intérêts crédit
    {
        "key": "lender.interest_share_rate",
        "group": "lender",
        "label": "Partage intérêts crédit (ratio)",
        "description": "Fraction des intérêts reversée aux prêteurs (0.5 = 50/50). 0 = legacy (coop garde tout).",
        "type": "decimal",
        "default": "0.5",
        "min": 0,
        "max": 1,
    },
    # LOT 10 — Avaliste
    {
        "key": "loans.avaliste.min_coverage_ratio",
        "group": "avaliste",
        "label": "Couverture min. avaliste (ratio)",
        "description": "(épargne_demandeur + épargne_avaliste) / montant_demande. 1.00 = 100 %.",
        "type": "decimal",
        "default": "1.00",
        "min": 0,
    },
    {
        "key": "loans.avaliste.allow_multiple",
        "group": "avaliste",
        "label": "Plusieurs avalistes autorisés",
        "description": "Si true, un crédit peut avoir plusieurs avalistes. Règle 2026 = false.",
        "type": "bool",
        "default": "false",
    },
    # LOT 11 — Campaign defaults
    {
        "key": "loans.campaign.default_montant_min",
        "group": "campaign",
        "label": "Plancher montant campagne (FCFA, défaut)",
        "description": "Valeur pré-remplie à la création d'une MicrocreditCampaign.",
        "type": "int",
        "default": "5000",
        "min": 0,
    },
    {
        "key": "loans.campaign.default_montant_max",
        "group": "campaign",
        "label": "Plafond montant campagne (FCFA, défaut)",
        "description": "Valeur pré-remplie à la création d'une MicrocreditCampaign.",
        "type": "int",
        "default": "50000",
        "min": 0,
    },
    {
        "key": "loans.campaign.default_taux",
        "group": "campaign",
        "label": "Taux campagne (ratio, défaut)",
        "description": "Pré-rempli pour la campagne. Standard 10 % = 0.10.",
        "type": "decimal",
        "default": "0.10",
        "min": 0,
        "max": 1,
    },
    {
        "key": "loans.campaign.default_recovery_days",
        "group": "campaign",
        "label": "Recouvrement (jours, défaut)",
        "description": "Durée par défaut du recouvrement par collectes journalières.",
        "type": "int",
        "default": "60",
        "min": 1,
    },
    # LOT 12 — Eligibility routing
    {
        "key": "loans.eligibility.allow_senior_brc",
        "group": "eligibility",
        "label": "Voie « Ancien » activée",
        "description": "Kill-switch voie 1 (Ancien BRC). False = bloque les demandes directes.",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "loans.eligibility.allow_avaliste",
        "group": "eligibility",
        "label": "Voie « Avaliste » activée",
        "description": "Kill-switch voie 2 (avec garant).",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "loans.eligibility.allow_campaign",
        "group": "eligibility",
        "label": "Voie « Micro-campagne » activée",
        "description": "Kill-switch voie 3 (campagne).",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "loans.eligibility.require_brc_for_senior",
        "group": "eligibility",
        "label": "Justificatif BRC obligatoire pour la voie « Ancien »",
        "description": "Défaut false : le BRC est documentaire, l'ancienneté seule ouvre la voie et le comité juge. True pour re-exiger un statut BRC validé.",
        "type": "bool",
        "default": "false",
    },
    {
        "key": "loans.eligibility.route_priority",
        "group": "eligibility",
        "label": "Ordre des voies (CSV)",
        "description": "Première voie qui matche gagne. Voie absente = désactivée.",
        "type": "csv",
        "default": "senior_brc,avaliste,campaign",
    },
    # LOT 13 — Seizure
    {
        "key": "loans.seizure.source_order",
        "group": "seizure",
        "label": "Ordre des sources (CSV)",
        "description": "Ordre du balayage saisie. Source absente = ignorée.",
        "type": "csv",
        "default": "borrower_classique,borrower_collecte,avaliste_classique,avaliste_collecte",
    },
    {
        "key": "loans.seizure.include_avaliste",
        "group": "seizure",
        "label": "Inclure l'avaliste à la saisie",
        "description": "Détermine si l'épargne du garant (avaliste) peut être mobilisée pour couvrir un crédit impayé.",
        "type": "bool",
        "default": "true",
    },
    {
        "key": "loans.seizure.exclude_engaged_tranches",
        "group": "seizure",
        "label": "Protéger l'épargne déjà engagée",
        "description": "Empêche la saisie de l'épargne déjà engagée dans le financement d'un autre crédit. À ne pas désactiver hors contrôle exceptionnel.",
        "type": "bool",
        "default": "true",
    },
    # LOT 14 — Judicial
    {
        "key": "loans.judicial_escalation.mode",
        "group": "judicial",
        "label": "Mode d'escalade judiciaire",
        "description": "manual (admin clique), auto (cron pose), hybrid (notif J-N puis pose).",
        "type": "enum",
        "default": "manual",
        "choices": ["manual", "auto", "hybrid"],
    },
    {
        "key": "loans.judicial_escalation.delay_days",
        "group": "judicial",
        "label": "Délai déclenchement auto (jours)",
        "description": "Jours entre l'échec de R1 et l'escalade auto (modes auto/hybrid).",
        "type": "int",
        "default": "60",
        "min": 0,
    },
    {
        "key": "loans.judicial_escalation.notify_before_days",
        "group": "judicial",
        "label": "Préavis admin (mode hybrid)",
        "description": "Jours avant déclenchement auto pendant lesquels l'admin peut intervenir.",
        "type": "int",
        "default": "7",
        "min": 0,
    },
]


# Index par clé pour validation des PATCH.
CATALOG_BY_KEY = {entry["key"]: entry for entry in CATALOG}


def is_known_key(key: str) -> bool:
    return key in CATALOG_BY_KEY


def get_entry(key: str) -> Optional[dict]:
    return CATALOG_BY_KEY.get(key)


def validate_value(entry: dict, value: str) -> tuple[bool, str]:
    """Valide ``value`` selon le ``type`` déclaré pour cette entrée.

    Renvoie ``(ok, message)``. ``ok=True`` → message vide. Sinon, message
    d'erreur lisible (sera renvoyé tel quel dans la response 400).
    """
    t = entry.get("type", "str")
    v = (value or "").strip()
    if t == "int":
        try:
            n = int(v)
        except (TypeError, ValueError):
            return False, "Valeur entière requise."
        mn = entry.get("min")
        mx = entry.get("max")
        if mn is not None and n < mn:
            return False, f"Doit être ≥ {mn}."
        if mx is not None and n > mx:
            return False, f"Doit être ≤ {mx}."
        return True, ""
    if t == "decimal":
        from decimal import Decimal, InvalidOperation

        try:
            d = Decimal(v)
        except (InvalidOperation, ValueError):
            return False, "Valeur décimale requise (ex. 0.10)."
        mn = entry.get("min")
        mx = entry.get("max")
        if mn is not None and d < Decimal(str(mn)):
            return False, f"Doit être ≥ {mn}."
        if mx is not None and d > Decimal(str(mx)):
            return False, f"Doit être ≤ {mx}."
        return True, ""
    if t == "bool":
        if v.lower() not in {"true", "false", "1", "0", "yes", "no"}:
            return False, "Valeur booléenne attendue (true/false)."
        return True, ""
    if t == "enum":
        choices = entry.get("choices", [])
        if v not in choices:
            return False, f"Doit être l'une de : {', '.join(choices)}."
        return True, ""
    if t == "csv":
        # Pas de contrainte stricte ici — la lib downstream filtre les
        # valeurs inconnues (cf. eligibility_routing._route_priority).
        return True, ""
    # str — pas de validation supplémentaire.
    return True, ""
