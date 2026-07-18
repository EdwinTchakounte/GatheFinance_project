"""Crée les comptes de test pour la recette manuelle.

Run :  python manage.py seed_test_accounts
Idempotent : peut être rejoué sans dupliquer les comptes.

Comptes créés
-------------

Staff (login sur http://localhost:3202/login + Django admin) :
    admin@gathe.test           / test1234    superuser + groupes admin/comite/staff
    comite@gathe.test          / test1234    staff + groupe comite (peut décider crédits)
    staff@gathe.test           / test1234    staff seul (lecture admin, ne décide pas)

Membres (login sur http://localhost:3201/connexion) :
    jean.kamga@test.local      / test1234    actif, 5 dépôts épargne (solde 65 000 XAF)
    marie.tankam@test.local    / test1234    actif, crédit en cours avec échéances
    paul.suspendu@test.local   / test1234    suspendu (n'a pas payé sa 1re cotisation)

+ 2 MembershipRequest « en_attente » pour tester l'approbation/rejet via la modale.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.members.models import Member, MembershipRequest
from apps_coop.savings.models import SavingsAccount, SavingsTransaction


User = get_user_model()


class Command(BaseCommand):
    help = "Seed reproducible test accounts (staff + membres + demandes en attente)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("→ Seed comptes de test…"))

        # 1) Groupes (créés à la volée s'ils n'existent pas)
        groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in ["admin", "comite", "staff", "member"]
        }

        # 2) Comptes staff
        admin = self._ensure_user(
            "admin@gathe.test",
            password="test1234",
            first_name="Admin",
            last_name="GATHE",
            is_staff=True,
            is_superuser=True,
        )
        admin.groups.add(groups["admin"], groups["comite"], groups["staff"])

        comite = self._ensure_user(
            "comite@gathe.test",
            password="test1234",
            first_name="Marc",
            last_name="Comité",
            is_staff=True,
            is_superuser=False,
        )
        comite.groups.add(groups["comite"], groups["staff"])

        staff = self._ensure_user(
            "staff@gathe.test",
            password="test1234",
            first_name="Sylvie",
            last_name="Staff",
            is_staff=True,
            is_superuser=False,
        )
        staff.groups.add(groups["staff"])

        # 3) Membre actif avec épargne
        jean = self._ensure_member(
            email="jean.kamga@test.local",
            password="test1234",
            prenom="Jean",
            nom="Kamga",
            numero="GF-2026-0001",
            statut=Member.Statut.ACTIF,
        )
        self._seed_savings(jean, deposits=[15000, 10000, 20000, 5000, 15000])

        # 4) Membre actif avec un crédit en cours
        marie = self._ensure_member(
            email="marie.tankam@test.local",
            password="test1234",
            prenom="Marie",
            nom="Tankam",
            numero="GF-2026-0002",
            statut=Member.Statut.ACTIF,
        )
        self._seed_savings(marie, deposits=[50000, 30000])
        self._seed_active_loan(marie)

        # 5) Membre suspendu (n'a pas payé sa 1re cotisation)
        self._ensure_member(
            email="paul.suspendu@test.local",
            password="test1234",
            prenom="Paul",
            nom="Mbida",
            numero="GF-2026-0003",
            statut=Member.Statut.SUSPENDU,
        )

        # 6) Demandes d'adhésion en attente (pour tester la modale d'approbation)
        for nom, prenom, email, city in [
            ("Tchamba", "Aline", "aline.tchamba@test.local", "Yaoundé"),
            ("Nguemo", "Bertrand", "bertrand.nguemo@test.local", "Bafoussam"),
        ]:
            MembershipRequest.objects.update_or_create(
                email=email,
                defaults={
                    "nom": nom,
                    "prenom": prenom,
                    "city": city,
                    "phone": "+237699000000",
                    "motivation": "Souhaite rejoindre la coopérative pour bâtir une épargne stable.",
                    "language": "fr",
                    "statut": MembershipRequest.Statut.EN_ATTENTE,
                },
            )

        self.stdout.write(self.style.SUCCESS("✓ Seed terminé. Identifiants imprimés ci-dessous."))
        self._print_credentials()

    # -- Helpers -----------------------------------------------------------

    def _ensure_user(
        self,
        email: str,
        *,
        password: str,
        first_name: str,
        last_name: str,
        is_staff: bool = False,
        is_superuser: bool = False,
    ):
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "is_active": True,
            },
        )
        # Always reset password to the known value (idempotence) — these are test accounts.
        user.set_password(password)
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = True
        user.save()
        action = "créé" if created else "mis à jour"
        self.stdout.write(f"  • User {email} {action}")
        return user

    def _ensure_member(
        self,
        *,
        email: str,
        password: str,
        prenom: str,
        nom: str,
        numero: str,
        statut: str,
    ) -> Member:
        user = self._ensure_user(email, password=password, first_name=prenom, last_name=nom)
        member_group, _ = Group.objects.get_or_create(name="member")
        user.groups.add(member_group)

        member, _ = Member.objects.get_or_create(
            user=user,
            defaults={
                "numero_membre": numero,
                "nom": nom,
                "prenom": prenom,
                "phone": "+237699111000",
                "statut": statut,
                "date_adhesion": date.today() - timedelta(days=60),
            },
        )
        # Re-sync mutable fields (statut peut avoir changé entre runs)
        member.numero_membre = numero
        member.statut = statut
        member.nom = nom
        member.prenom = prenom
        member.save()

        SavingsAccount.objects.get_or_create(
            member=member,
            defaults={
                "solde": Decimal("0"),
                "date_ouverture": member.date_adhesion,
                "taux_interet_applique": Decimal("0.0350"),
            },
        )
        return member

    def _seed_savings(self, member: Member, *, deposits: list[int]) -> None:
        """Crée N transactions de dépôt et réajuste le solde — idempotent."""
        account = SavingsAccount.objects.get(member=member)
        # Reset à zéro pour la rejouabilité
        SavingsTransaction.objects.filter(account=account).delete()
        account.solde = Decimal("0")
        account.save(update_fields=["solde"])

        solde = Decimal("0")
        base_date = timezone.now() - timedelta(days=len(deposits) * 7)
        for i, montant in enumerate(deposits, start=1):
            amt = Decimal(montant)
            solde += amt
            SavingsTransaction.objects.create(
                account=account,
                type_op=SavingsTransaction.TypeOp.DEPOT,
                montant=amt,
                solde_apres=solde,
                date=base_date + timedelta(days=i * 7),
            )
        account.solde = solde
        account.save(update_fields=["solde"])
        self.stdout.write(f"  • Épargne {member.numero_membre} : {len(deposits)} dépôts, solde {solde} XAF")

    def _seed_active_loan(self, member: Member) -> None:
        """Crée une LoanRequest approuvée + un Loan actif + 12 échéances."""
        if Loan.objects.filter(member=member).exists():
            return  # idempotent

        loan_request = LoanRequest.objects.create(
            member=member,
            montant_demande=Decimal("500000"),
            duree_mois=12,
            motif="Achat de matériel pour la boutique.",
            statut=LoanRequest.Statut.APPROUVEE,
            date_decision=timezone.now() - timedelta(days=30),
        )

        loan = Loan.objects.create(
            member=member,
            loan_request=loan_request,
            numero_dossier="GF-CR-2026-0001",
            montant=Decimal("500000"),
            taux_interet=Decimal("0.10"),
            duree_mois=12,
            date_decaissement=date.today() - timedelta(days=30),
            date_premiere_echeance=date.today() + timedelta(days=1),
            montant_total_du=Decimal("560000"),
            solde_restant=Decimal("560000"),
            statut=Loan.Statut.ACTIF,
        )

        # Échéancier constant approximatif (46 667 / mois, dernier arrondi)
        montant_total = Decimal("560000")
        n = 12
        per = (montant_total / n).quantize(Decimal("0.01"))
        cumul = Decimal("0")
        for i in range(1, n + 1):
            if i == n:
                montant_periode = montant_total - cumul
            else:
                montant_periode = per
                cumul += per
            LoanInstallment.objects.create(
                loan=loan,
                numero_echeance=i,
                date_echeance=loan.date_premiere_echeance + timedelta(days=(i - 1) * 30),
                montant_capital=(montant_periode * Decimal("0.85")).quantize(Decimal("0.01")),
                montant_interets=(montant_periode * Decimal("0.15")).quantize(Decimal("0.01")),
                montant_total=montant_periode,
                montant_paye=Decimal("0"),
                statut=LoanInstallment.Statut.A_VENIR,
            )
        self.stdout.write(f"  • Crédit {loan.numero_dossier} ({n} échéances) attaché à {member.numero_membre}")

    def _print_credentials(self) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Comptes de test (mot de passe : test1234)"))
        self.stdout.write("─" * 78)
        rows = [
            ("Staff (admin Next.js + Django admin)", ""),
            ("  admin@gathe.test", "superuser — voit tout, peut tout"),
            ("  comite@gathe.test", "comité crédit — décide les demandes"),
            ("  staff@gathe.test", "staff lecture (KPIs, listes)"),
            ("", ""),
            ("Membres (portail port 3201)", ""),
            ("  jean.kamga@test.local", "actif · 65 000 XAF d'épargne · GF-2026-0001"),
            ("  marie.tankam@test.local", "actif · crédit 500 000 XAF en cours · GF-2026-0002"),
            ("  paul.suspendu@test.local", "suspendu · doit payer sa 1re cotisation"),
            ("", ""),
            ("Demandes en attente (à approuver côté admin)", ""),
            ("  aline.tchamba@test.local", "demande #1 — en_attente"),
            ("  bertrand.nguemo@test.local", "demande #2 — en_attente"),
        ]
        for left, right in rows:
            if not left and not right:
                self.stdout.write("")
            else:
                self.stdout.write(f"  {left:<32} {right}")
        self.stdout.write("─" * 78)
