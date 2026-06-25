"""Seed 3 campagnes micro-crédit de démo (refonte 2026 §8 / LOT 11).

Crée des campagnes ciblées sur 3 profils différents — commerçants, agriculteurs,
parents — avec montants et durées réalistes inspirés du règlement intérieur.

Run :  python manage.py seed_demo_campaigns
       python manage.py seed_demo_campaigns --force   (replace existing demos)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps_coop.loans.models import MicrocreditCampaign


User = get_user_model()


CAMPAIGNS = [
    {
        "nom": "Campagne commerçants Akwa",
        "profil_cible": "commercants",
        "days_offset_start": -7,        # commencée il y a 1 semaine
        "days_offset_end": 30,          # encore 30 jours
        "montant_min": 25000,
        "montant_max": 100000,
        "taux_interet": Decimal("0.10"),  # 10 % flat
        "nb_jours_recouvrement": 60,
        "plafond_beneficiaires": 30,
    },
    {
        "nom": "Campagne rentrée scolaire 2026",
        "profil_cible": "parents",
        "days_offset_start": 0,         # ouvre aujourd'hui
        "days_offset_end": 45,
        "montant_min": 15000,
        "montant_max": 75000,
        "taux_interet": Decimal("0.10"),
        "nb_jours_recouvrement": 90,
        "plafond_beneficiaires": 50,
    },
    {
        "nom": "Campagne agriculteurs Douala-Centre",
        "profil_cible": "agriculteurs",
        "days_offset_start": -3,
        "days_offset_end": 60,
        "montant_min": 50000,
        "montant_max": 200000,
        "taux_interet": Decimal("0.10"),
        "nb_jours_recouvrement": 120,
        "plafond_beneficiaires": 20,
    },
]


class Command(BaseCommand):
    help = "Seed des campagnes micro-crédit de démo (3 profils différents)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Supprime les campagnes existantes portant les mêmes noms avant "
                "de recréer (utile pour réinitialiser une démo)."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = bool(options.get("force"))

        # Auteur — superuser créé par seed_test_accounts, sinon tombe sur le 1er.
        author = (
            User.objects.filter(email="admin@gathe.test").first()
            or User.objects.filter(is_superuser=True).order_by("pk").first()
        )
        if author is None:
            self.stderr.write(self.style.ERROR(
                "Aucun superuser trouvé — lance d'abord `seed_test_accounts`.",
            ))
            return

        created = 0
        skipped = 0
        replaced = 0
        today = date.today()
        for spec in CAMPAIGNS:
            existing = MicrocreditCampaign.objects.filter(nom=spec["nom"]).first()
            if existing is not None and not force:
                skipped += 1
                self.stdout.write(f"  ↷ {spec['nom']!r} existe déjà — skip.")
                continue
            if existing is not None:
                existing.delete()
                replaced += 1

            MicrocreditCampaign.objects.create(
                nom=spec["nom"],
                profil_cible=spec["profil_cible"],
                date_debut=today + timedelta(days=spec["days_offset_start"]),
                date_fin=today + timedelta(days=spec["days_offset_end"]),
                montant_min=Decimal(spec["montant_min"]),
                montant_max=Decimal(spec["montant_max"]),
                taux_interet=spec["taux_interet"],
                nb_jours_recouvrement=spec["nb_jours_recouvrement"],
                plafond_beneficiaires=spec["plafond_beneficiaires"],
                actif=True,
                created_by=author,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {spec['nom']!r} (profil_cible={spec['profil_cible']}, "
                f"montant ≤ {spec['montant_max']} XAF, taux 10 %)",
            ))

        active_now = MicrocreditCampaign.objects.filter(
            actif=True,
            date_debut__lte=today,
            date_fin__gte=today,
        ).count()
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Récapitulatif"))
        self.stdout.write(f"  Créées : {created} · Remplacées : {replaced} · Ignorées : {skipped}")
        self.stdout.write(f"  Campagnes actives à ce jour : {active_now}")
