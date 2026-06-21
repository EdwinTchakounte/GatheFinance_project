"""Seed de comptes membres avec des crédits dans 4 états différents.

Run :  python manage.py seed_demo_credits

Crée 4 nouveaux comptes (en plus de ceux de ``seed_test_accounts``) pour
peupler la démo crédit côté mobile + admin :

    nadine.fotso@test.local      / test1234   crédit ACTIF, fraîchement décaissé
    eric.muna@test.local         / test1234   crédit ACTIF, 1 échéance déjà payée
    claire.ndongo@test.local     / test1234   crédit EN_RETARD (échéance dépassée)
    david.nyamsi@test.local      / test1234   crédit CLOTURE (historique)

Idempotent : skip si un Loan existe déjà pour ce membre.

CH-11 — Tous les crédits sont en mode ``source`` (intérêts retenus à la mise
à disposition). Les échéances ne contiennent QUE du capital, pas d'intérêts.

Règle métier — un membre ne peut avoir qu'UN SEUL crédit actif à la fois
(``loans/services.py`` ``compute_eligibility``). On respecte cette contrainte :
chaque démo a au plus 1 Loan non clôturé.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.contrib.auth.models import Group

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.members.models import Member
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount

User = get_user_model()


class Command(BaseCommand):
    help = "Crée 4 comptes membres avec des crédits dans 4 états différents (ACTIF, ACTIF avec versement, EN_RETARD, CLOTURE)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seed crédits de démo"))
        self.stdout.write("─" * 72)

        # 1. Crédit ACTIF récent (fraîchement décaissé, aucune échéance payée)
        nadine = self._ensure_member(
            email="nadine.fotso@test.local",
            password="test1234",
            prenom="Nadine",
            nom="Fotso",
            numero="GF-2026-1001",
        )
        self._seed_loan(
            member=nadine,
            numero_dossier="GF-CR-2026-DEMO-01",
            montant=Decimal("100000"),
            duree_mois=3,
            days_since_disbursement=2,
            installments_paid=0,
            statut=Loan.Statut.ACTIF,
        )

        # 2. Crédit ACTIF, 1 échéance déjà payée
        eric = self._ensure_member(
            email="eric.muna@test.local",
            password="test1234",
            prenom="Eric",
            nom="Muna",
            numero="GF-2026-1002",
        )
        self._seed_loan(
            member=eric,
            numero_dossier="GF-CR-2026-DEMO-02",
            montant=Decimal("200000"),
            duree_mois=3,
            days_since_disbursement=35,
            installments_paid=1,
            statut=Loan.Statut.ACTIF,
        )

        # 3. Crédit EN_RETARD (échéance dépassée, non payée)
        claire = self._ensure_member(
            email="claire.ndongo@test.local",
            password="test1234",
            prenom="Claire",
            nom="Ndongo",
            numero="GF-2026-1003",
        )
        self._seed_loan(
            member=claire,
            numero_dossier="GF-CR-2026-DEMO-03",
            montant=Decimal("50000"),
            duree_mois=2,
            days_since_disbursement=40,
            installments_paid=0,
            statut=Loan.Statut.EN_RETARD,
        )

        # 4. Crédit CLOTURE (historique, toutes échéances payées)
        david = self._ensure_member(
            email="david.nyamsi@test.local",
            password="test1234",
            prenom="David",
            nom="Nyamsi",
            numero="GF-2026-1004",
        )
        self._seed_loan(
            member=david,
            numero_dossier="GF-CR-2026-DEMO-04",
            montant=Decimal("80000"),
            duree_mois=2,
            days_since_disbursement=90,
            installments_paid=2,  # toutes
            statut=Loan.Statut.CLOTURE,
        )

        self.stdout.write("─" * 72)
        self.stdout.write(
            self.style.SUCCESS(
                "Comptes de démo crédit prêts. Mot de passe : test1234"
            )
        )
        self.stdout.write("  nadine.fotso@test.local    actif, crédit 100 000 récent")
        self.stdout.write("  eric.muna@test.local       actif, crédit 200 000 (1 versement)")
        self.stdout.write("  claire.ndongo@test.local   actif, crédit 50 000 EN RETARD")
        self.stdout.write("  david.nyamsi@test.local    actif, crédit 80 000 CLOTURÉ")

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _ensure_member(
        self,
        *,
        email: str,
        password: str,
        prenom: str,
        nom: str,
        numero: str,
    ) -> Member:
        """Crée user + Member ACTIF + compte épargne s'ils n'existent pas. Idempotent."""
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=prenom,
                last_name=nom,
            )
        member_group, _ = Group.objects.get_or_create(name="member")
        user.groups.add(member_group)

        member, created = Member.objects.get_or_create(
            user=user,
            defaults={
                "numero_membre": numero,
                "nom": nom,
                "prenom": prenom,
                "phone": "+237699111000",
                "statut": Member.Statut.ACTIF,
                "date_adhesion": date.today() - timedelta(days=180),
            },
        )
        # Re-sync mutable fields pour les reruns
        member.numero_membre = numero
        member.statut = Member.Statut.ACTIF
        member.nom = nom
        member.prenom = prenom
        member.save()

        # Compte cotisation (SavingsAccount) — utilisé par compute_eligibility
        # (règle 4 : solde >= 100 XAF) et par la page Mes états du mobile.
        SavingsAccount.objects.get_or_create(
            member=member,
            defaults={
                "solde": Decimal("25000"),
                "date_ouverture": member.date_adhesion,
                "taux_interet_applique": Decimal("0.0100"),
            },
        )
        # Compte épargne classique — c'est ce solde qui s'affiche dans le
        # hero de la Home mobile (label "Mon épargne"). Sans ça l'utilisateur
        # voit 0 XAF même s'il a un crédit en cours.
        ClassicSavingsAccount.objects.get_or_create(
            member=member,
            defaults={
                "solde": Decimal("75000"),
                "date_ouverture": member.date_adhesion,
            },
        )
        if created:
            self.stdout.write(f"  ✓ Membre créé : {prenom} {nom} ({member.numero_membre})")
        return member

    def _seed_loan(
        self,
        *,
        member: Member,
        numero_dossier: str,
        montant: Decimal,
        duree_mois: int,
        days_since_disbursement: int,
        installments_paid: int,
        statut: str,
    ) -> None:
        """Crée un Loan + son échéancier.

        Règle CH-11 — mode ``source`` :
            * ``interets_retenus_source`` = montant × 0.10
            * ``montant_decaisse_net`` = montant - intérêts
            * ``montant_total_du`` = montant (capital pur à rembourser)
            * échéancier réparti uniquement sur le capital
        """
        if Loan.objects.filter(member=member).exists():
            self.stdout.write(f"  · Loan déjà présent pour {member.numero_membre}, skip")
            return

        date_decaissement = date.today() - timedelta(days=days_since_disbursement)
        interets_source = (montant * Decimal("0.10")).quantize(Decimal("0.01"))
        net_decaisse = montant - interets_source

        loan_request = LoanRequest.objects.create(
            member=member,
            montant_demande=montant,
            duree_mois=duree_mois,
            motif="Crédit de démo seedé pour test fonctionnel.",
            statut=LoanRequest.Statut.APPROUVEE,
            date_decision=timezone.now() - timedelta(days=days_since_disbursement + 1),
        )

        loan = Loan.objects.create(
            member=member,
            loan_request=loan_request,
            numero_dossier=numero_dossier,
            montant=montant,
            taux_interet=Decimal("0.1000"),
            taux_penalite=Decimal("0.5000"),
            duree_mois=duree_mois,
            modalite_paiement="mensuel",
            date_decaissement=date_decaissement,
            date_premiere_echeance=date_decaissement + timedelta(days=30),
            date_butoire=date_decaissement + timedelta(days=duree_mois * 30 + 15),
            montant_total_du=montant,  # CH-11 : capital pur, sans intérêts
            solde_restant=montant if statut != Loan.Statut.CLOTURE else Decimal("0"),
            statut=statut,
            mode_retenue_interets=Loan.ModeRetenue.SOURCE,
            montant_decaisse_net=net_decaisse,
            interets_retenus_source=interets_source,
        )

        # Échéancier : capital réparti uniformément
        per_capital = (montant / duree_mois).quantize(Decimal("0.01"))
        cumul = Decimal("0")
        for i in range(1, duree_mois + 1):
            if i == duree_mois:
                montant_periode = montant - cumul
            else:
                montant_periode = per_capital
                cumul += per_capital

            # Statut de l'échéance
            is_paid = i <= installments_paid
            if statut == Loan.Statut.CLOTURE:
                inst_statut = LoanInstallment.Statut.PAYEE
                montant_paye = montant_periode
            elif is_paid:
                inst_statut = LoanInstallment.Statut.PAYEE
                montant_paye = montant_periode
            elif statut == Loan.Statut.EN_RETARD and i == installments_paid + 1:
                inst_statut = LoanInstallment.Statut.EN_RETARD
                montant_paye = Decimal("0")
            else:
                inst_statut = LoanInstallment.Statut.A_VENIR
                montant_paye = Decimal("0")

            LoanInstallment.objects.create(
                loan=loan,
                numero_echeance=i,
                date_echeance=loan.date_premiere_echeance + timedelta(days=(i - 1) * 30),
                montant_capital=montant_periode,
                montant_interets=Decimal("0"),  # CH-11 : 0 dans l'échéance
                montant_total=montant_periode,
                montant_paye=montant_paye,
                statut=inst_statut,
            )

        # Recalcule solde_restant à partir des installments réellement payés
        if statut != Loan.Statut.CLOTURE:
            total_paye = (per_capital * installments_paid).quantize(Decimal("0.01"))
            loan.solde_restant = montant - total_paye
            loan.save(update_fields=["solde_restant"])

        self.stdout.write(
            f"  ✓ Crédit {numero_dossier} · {montant} XAF · {duree_mois} mois · {statut} "
            f"({installments_paid}/{duree_mois} payées)"
        )
