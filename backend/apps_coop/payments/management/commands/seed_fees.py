"""Seed des FeeType selon le Règlement Intérieur 2025.

Idempotent : ne crée que les codes manquants, ne touche pas aux montants
existants (l'admin peut les éditer librement après le seed initial).

Montants (Articles 1, 4) :
    - INSCRIPTION    :  2 000 FCFA (Article 1)
    - ADHESION       : 10 000 FCFA (Article 1, versement unique)
    - CARNET         :  1 000 FCFA (Article 4, carnet de collecte)

Les autres codes (DEMANDE_CREDIT, RECONDUCTION) ne sont pas chiffrés par le
règlement : on les crée à 0 si absents pour qu'un admin puisse les fixer.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.payments.models import FeeType, RateParam


# Frais imposés par le Règlement Intérieur (montants exacts, non négociables).
REGULATION_FEES: dict[str, tuple[str, Decimal]] = {
    FeeType.Code.ADHESION:    ("Frais d'adhésion",     Decimal("10000")),
    FeeType.Code.INSCRIPTION: ("Frais d'inscription",  Decimal("2000")),
    FeeType.Code.CARNET:      ("Frais de carnet",      Decimal("1000")),
}

# Frais non chiffrés par le règlement — créés à 0 si absents, jamais écrasés.
DISCRETIONARY_FEES: dict[str, tuple[str, Decimal]] = {
    FeeType.Code.DEMANDE_CREDIT: ("Frais de demande de crédit", Decimal("0")),
    FeeType.Code.RECONDUCTION:   ("Frais de reconduction",      Decimal("0")),
    # Carnets des collectes particulières (un carnet distinct par type). Défaut
    # aligné sur le carnet collecte (1 000) ; l'admin ajuste dans la page Coûts.
    FeeType.Code.CARNET_TONTINE: ("Frais de carnet tontine",         Decimal("1000")),
    FeeType.Code.CARNET_CAISSE:  ("Frais de carnet caisse scolaire", Decimal("1000")),
}


class Command(BaseCommand):
    help = (
        "Aligne les FeeType sur le Règlement Intérieur "
        "(adhésion 10 000, inscription 2 000, carnet 1 000) et crée les "
        "frais discrétionnaires manquants à 0. Idempotent."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Frais réglementaires — toujours alignés sur la valeur officielle.
        for code, (libelle, montant) in REGULATION_FEES.items():
            fee, was_created = FeeType.objects.get_or_create(
                code=code,
                defaults={"libelle": libelle, "montant": montant, "actif": True},
            )
            if was_created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Created  {code:<22} → {montant} FCFA")
                )
            elif fee.montant != montant:
                old = fee.montant
                fee.montant = montant
                fee.libelle = libelle
                fee.actif = True
                fee.save(update_fields=["montant", "libelle", "actif", "updated_at"])
                self.stdout.write(
                    self.style.WARNING(
                        f"  ⚙ Aligned  {code:<22} {old} → {montant} FCFA (règlement)"
                    )
                )
            else:
                self.stdout.write(f"  · Kept     {code:<22} → {fee.montant} FCFA")

        # 2) Frais discrétionnaires — créés si absents, jamais réécrits.
        for code, (libelle, montant) in DISCRETIONARY_FEES.items():
            fee, was_created = FeeType.objects.get_or_create(
                code=code,
                defaults={"libelle": libelle, "montant": montant, "actif": True},
            )
            if was_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Created  {code:<22} → {montant} FCFA (admin to fix)"
                    )
                )
            else:
                self.stdout.write(
                    f"  · Kept     {code:<22} → {fee.montant} FCFA (admin-edited)"
                )

        # 3) Taux de frais de transaction sur versement — créé à 3 % si absent,
        #    jamais réécrit (l'admin l'ajuste ensuite sur la page Coûts).
        rate, was_created = RateParam.objects.get_or_create(
            code=RateParam.Code.TRANSACTION_FEE,
            defaults={
                "libelle": "Frais de transaction sur versement (%)",
                "valeur": Decimal("0.03"),
                "actif": True,
            },
        )
        if was_created:
            self.stdout.write(
                self.style.SUCCESS(
                    "  ✓ Created  TRANSACTION_FEE        → 3 % (versement)"
                )
            )
        else:
            self.stdout.write(
                f"  · Kept     TRANSACTION_FEE        → {rate.valeur} (admin-edited)"
            )

        self.stdout.write(self.style.SUCCESS("Seed fees done."))
