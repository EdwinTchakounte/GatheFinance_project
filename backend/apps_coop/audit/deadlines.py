"""Échéances des processus métier — alimente l'onglet « Notifications » admin.

Le tableau de bord montrait l'état des choses, jamais **ce qui arrive à
terme**. Résultat : une campagne dont la date de fin est passée reste ouverte,
un cycle de collecte se prolonge, des crédits dépassent leur date butoire, des
réinscriptions tombent — et personne ne le voit tant qu'un membre ne se plaint
pas. Ce module rassemble ces échéances au même endroit.

Principe : **lecture seule, agrégée, sans effet de bord**. Aucune de ces
fonctions ne modifie quoi que ce soit ni n'envoie de notification ; ce sont les
crons qui agissent. L'onglet ne fait que rendre visible ce qui vient.

Chaque processus renvoie une carte homogène ::

    {
      "cle": "credit.echeance_depassee",
      "titre": "Crédits au-delà de leur date butoire",
      "description": "…",
      "date_echeance": "2026-09-01" | None,
      "jours_restants": -7,          # négatif = dépassé
      "en_retard": True,
      "gravite": "urgent" | "proche" | "info",
      "volume": 3,                   # nombre d'éléments concernés
      "unite": "crédits",
      "lien": "/loans",              # écran admin où agir
    }

``volume == 0`` ne fait pas disparaître la carte : savoir qu'il n'y a rien à
traiter est une information, et une carte qui disparaît laisse croire à un
oubli.
"""
from __future__ import annotations

from datetime import date, timedelta

from django.utils import timezone

#: Au-delà, une échéance n'est pas encore « à l'ordre du jour ».
DEFAULT_HORIZON_DAYS = 30
#: En deçà, l'échéance passe en « proche » (orange).
SOON_DAYS = 7


def _gravite(jours_restants: int | None) -> str:
    if jours_restants is None:
        return "info"
    if jours_restants < 0:
        return "urgent"
    if jours_restants <= SOON_DAYS:
        return "proche"
    return "info"


def _carte(
    cle: str,
    titre: str,
    description: str,
    *,
    echeance: date | None,
    volume: int,
    unite: str,
    lien: str,
    today: date,
) -> dict:
    jours = (echeance - today).days if echeance is not None else None
    return {
        "cle": cle,
        "titre": titre,
        "description": description,
        "date_echeance": echeance.isoformat() if echeance else None,
        "jours_restants": jours,
        "en_retard": bool(jours is not None and jours < 0),
        # Une carte sans rien à traiter reste « info », même si sa date est
        # passée : c'est le volume qui rend une échéance actionnable.
        "gravite": _gravite(jours) if volume else "info",
        "volume": volume,
        "unite": unite,
        "lien": lien,
    }


def _premier_du_mois_suivant(today: date) -> date:
    return (today.replace(day=1) + timedelta(days=32)).replace(day=1)


def collect_deadlines(*, horizon_days: int = DEFAULT_HORIZON_DAYS) -> list[dict]:
    """Toutes les échéances de processus, triées par urgence.

    Les imports sont faits ici (et non au module) pour éviter les cycles entre
    ``audit`` et les apps métier qu'il observe.
    """
    from apps_coop.loans.models import Loan, MicrocreditCampaign
    from apps_coop.members.models import Member
    from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
    from apps_coop.special_collections.models import SpecialCollectionCycle

    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)
    cartes: list[dict] = []

    # 1) Clôture mensuelle des collectes journalières (cron du 1er à 02:00).
    #    On compte les comptes qui porteront un solde à restituer.
    prochaine_cloture = _premier_du_mois_suivant(today)
    cartes.append(
        _carte(
            "collecte.fin_de_mois",
            "Clôture mensuelle des collectes",
            "Commission prélevée puis solde restitué (espèces, Mobile Money "
            "ou bascule en épargne) selon la préférence de chaque membre.",
            echeance=prochaine_cloture,
            volume=SavingsAccount.objects.filter(solde__gt=0).count(),
            unite="comptes approvisionnés",
            lien="/collecte-preferences",
            today=today,
        )
    )

    # 2) Crédits dont la date butoire est DÉPASSÉE — pénalité globale et
    #    contentieux se déclenchent à partir de là.
    en_cours = [Loan.Statut.ACTIF, Loan.Statut.EN_RETARD, Loan.Statut.CONTENTIEUX]
    depasses = Loan.objects.filter(
        statut__in=en_cours,
        en_attente_decaissement=False,
        date_butoire__lt=today,
    )
    plus_ancienne = (
        depasses.order_by("date_butoire")
        .values_list("date_butoire", flat=True)
        .first()
    )
    cartes.append(
        _carte(
            "credit.echeance_depassee",
            "Crédits au-delà de leur date butoire",
            "Le délai formel de remboursement est écoulé : pénalité globale "
            "puis bascule en contentieux.",
            echeance=plus_ancienne,
            volume=depasses.count(),
            unite="crédits",
            lien="/loans?statut=en_retard",
            today=today,
        )
    )

    # 3) Crédits dont la date butoire approche.
    proches = Loan.objects.filter(
        statut__in=en_cours,
        en_attente_decaissement=False,
        date_butoire__gte=today,
        date_butoire__lte=horizon,
    )
    prochaine = (
        proches.order_by("date_butoire").values_list("date_butoire", flat=True).first()
    )
    cartes.append(
        _carte(
            "credit.echeance_proche",
            "Crédits arrivant à échéance",
            f"Date butoire atteinte dans les {horizon_days} jours — relancer "
            "avant que la pénalité ne s'applique.",
            echeance=prochaine,
            volume=proches.count(),
            unite="crédits",
            lien="/loans",
            today=today,
        )
    )

    # 4) Campagnes micro-crédit : encore actives alors que la date de fin est
    #    passée, ou sur le point de se terminer.
    camp_echues = MicrocreditCampaign.objects.filter(actif=True, date_fin__lt=today)
    camp_fin_ancienne = (
        camp_echues.order_by("date_fin").values_list("date_fin", flat=True).first()
    )
    cartes.append(
        _carte(
            "campagne.echue",
            "Campagnes échues encore ouvertes",
            "Leur date de fin est passée mais elles acceptent toujours des "
            "candidatures — à clôturer.",
            echeance=camp_fin_ancienne,
            volume=camp_echues.count(),
            unite="campagnes",
            lien="/campaigns",
            today=today,
        )
    )

    camp_proches = MicrocreditCampaign.objects.filter(
        actif=True, date_fin__gte=today, date_fin__lte=horizon,
    )
    cartes.append(
        _carte(
            "campagne.fin_proche",
            "Campagnes bientôt terminées",
            f"Fin prévue dans les {horizon_days} jours.",
            echeance=(
                camp_proches.order_by("date_fin")
                .values_list("date_fin", flat=True)
                .first()
            ),
            volume=camp_proches.count(),
            unite="campagnes",
            lien="/campaigns",
            today=today,
        )
    )

    # 5) Cycles de collectes particulières (caisse scolaire / tontine) ouverts
    #    au-delà de leur date de fin.
    cycles = SpecialCollectionCycle.objects.filter(
        statut=SpecialCollectionCycle.Statut.OUVERT,
        date_fin__isnull=False,
        date_fin__lte=horizon,
    )
    cartes.append(
        _carte(
            "collecte_particuliere.fin_cycle",
            "Cycles de collecte à clôturer",
            "Caisse scolaire / tontine dont la date de fin est atteinte ou "
            "proche — la clôture fige les soldes et ouvre la restitution.",
            echeance=(
                cycles.order_by("date_fin").values_list("date_fin", flat=True).first()
            ),
            volume=cycles.count(),
            unite="cycles",
            lien="/special-collections",
            today=today,
        )
    )

    # 6) Épargne classique arrivant à maturité (contrat 12 mois).
    maturites = ClassicSavingsAccount.objects.filter(
        date_prochaine_maturite__isnull=False,
        date_prochaine_maturite__lte=horizon,
    )
    cartes.append(
        _carte(
            "epargne.maturite",
            "Épargnes classiques à maturité",
            "Fin du contrat : restitution intégrale + frais de ré-inscription, "
            "puis archivage passé le délai de grâce.",
            echeance=(
                maturites.order_by("date_prochaine_maturite")
                .values_list("date_prochaine_maturite", flat=True)
                .first()
            ),
            volume=maturites.count(),
            unite="comptes",
            lien="/renewals",
            today=today,
        )
    )

    # 7) Réinscriptions annuelles des membres (anniversaire + 365 j).
    #    Le calcul vit dans une property Python, donc on borne d'abord en SQL
    #    sur la date de référence pour ne pas balayer toute la table.
    limite_base = horizon - timedelta(days=365)
    candidats = Member.objects.filter(
        statut=Member.Statut.ACTIF,
        date_derniere_reinscription__isnull=False,
        date_derniere_reinscription__lte=limite_base,
    ).only("id", "date_derniere_reinscription")
    dues = [m.prochaine_reinscription_due for m in candidats]
    dues = [d for d in dues if d is not None and d <= horizon]
    cartes.append(
        _carte(
            "membre.reinscription",
            "Réinscriptions annuelles dues",
            "Anniversaire d'adhésion atteint ou proche — sans re-souscription, "
            "le compte finit suspendu après le délai de grâce.",
            echeance=min(dues) if dues else None,
            volume=len(dues),
            unite="membres",
            lien="/renewals",
            today=today,
        )
    )

    # Tri : ce qui brûle d'abord, puis par date, puis par volume décroissant.
    ordre = {"urgent": 0, "proche": 1, "info": 2}
    cartes.sort(
        key=lambda c: (
            ordre.get(c["gravite"], 3),
            c["date_echeance"] or "9999-12-31",
            -c["volume"],
        )
    )
    return cartes


def deadlines_summary(cartes: list[dict]) -> dict:
    """Compteurs d'en-tête (pastille du sidebar, bandeau de la page)."""
    return {
        "urgent": sum(1 for c in cartes if c["gravite"] == "urgent"),
        "proche": sum(1 for c in cartes if c["gravite"] == "proche"),
        "total_elements": sum(c["volume"] for c in cartes),
        # Ce qui appelle une action MAINTENANT : dépassé et non vide.
        "a_traiter": sum(c["volume"] for c in cartes if c["gravite"] == "urgent"),
    }
