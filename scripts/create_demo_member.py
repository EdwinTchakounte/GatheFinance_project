"""Crée / met à jour UN compte MEMBRE de démonstration pour la revue Google Play.

- Non destructif, idempotent (rejouable sans doublon).
- Compte MEMBRE uniquement (is_staff=False, is_superuser=False) — aucun accès admin.
- Statut ACTIF (login possible) + un peu d'épargne pour que l'app ne soit pas vide.

Identifiants (surchargeables par variables d'env) :
    GATHE_DEMO_EMAIL     (défaut: demo@gathe-finance.com)
    GATHE_DEMO_PASSWORD  (défaut: GatheDemo2026!)
    GATHE_DEMO_NUMERO    (défaut: GF-DEMO-0001)

Usage (dans le conteneur backend) :
    python manage.py shell < create_demo_member.py
    GATHE_DEMO_PASSWORD='MonMotDePasse' python manage.py shell < create_demo_member.py
"""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from apps_coop.members.models import Member
from apps_coop.savings.models import SavingsAccount, SavingsTransaction

User = get_user_model()

EMAIL = os.environ.get("GATHE_DEMO_EMAIL", "demo@gathe-finance.com")
PASSWORD = os.environ.get("GATHE_DEMO_PASSWORD", "GatheDemo2026!")
NUMERO = os.environ.get("GATHE_DEMO_NUMERO", "GF-DEMO-0001")

with transaction.atomic():
    user, created = User.objects.get_or_create(
        username=EMAIL,
        defaults={"email": EMAIL, "is_active": True},
    )
    user.email = EMAIL
    user.first_name = "Démo"
    user.last_name = "Play Store"
    user.is_staff = False       # jamais d'accès admin
    user.is_superuser = False
    user.is_active = True
    user.set_password(PASSWORD)
    user.save()

    member_group, _ = Group.objects.get_or_create(name="member")
    user.groups.add(member_group)

    member, _ = Member.objects.get_or_create(
        user=user,
        defaults={
            "numero_membre": NUMERO,
            "nom": "Play Store",
            "prenom": "Démo",
            "phone": "+237600000000",
            "statut": Member.Statut.ACTIF,
            "date_adhesion": date.today() - timedelta(days=90),
        },
    )
    member.numero_membre = NUMERO
    member.statut = Member.Statut.ACTIF
    member.nom = "Play Store"
    member.prenom = "Démo"
    member.save()

    account, _ = SavingsAccount.objects.get_or_create(
        member=member,
        defaults={
            "solde": Decimal("0"),
            "date_ouverture": member.date_adhesion,
            "taux_interet_applique": Decimal("0.0350"),
        },
    )
    # Quelques dépôts pour que le testeur voie une app peuplée (si vide).
    if not SavingsTransaction.objects.filter(account=account).exists():
        solde = Decimal("0")
        base = timezone.now() - timedelta(days=35)
        for i, montant in enumerate([15000, 10000, 20000, 5000, 15000], start=1):
            solde += Decimal(montant)
            SavingsTransaction.objects.create(
                account=account,
                type_op=SavingsTransaction.TypeOp.DEPOT,
                montant=Decimal(montant),
                solde_apres=solde,
                date=base + timedelta(days=i * 5),
            )
        account.solde = solde
        account.save(update_fields=["solde"])

print("=" * 56)
print("COMPTE DÉMO PLAY STORE prêt (" + ("créé" if created else "mis à jour") + ")")
print("  email    :", EMAIL)
print("  password :", PASSWORD)
print("  membre   :", member.numero_membre, "-", member.statut)
print("  épargne  :", account.solde, "XAF")
print("  is_staff :", user.is_staff, "| is_superuser:", user.is_superuser)
print("=" * 56)
