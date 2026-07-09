"""Seed démo riche pour illustrer le dashboard admin 2026.

Run :  python manage.py seed_demo_dashboard
Idempotent : peut être rejoué (clean partiel des données démo, jamais des
comptes utilisateurs des autres seeds).

Crée des données qui peuplent les **14 KPIs** du dashboard refonte 2026 :

  - Membres : actifs / suspendus / temporaires / BRC validés
  - Adhésions à instruire (MembershipRequest EN_ATTENTE)
  - Crédits en instruction (LoanRequest EN_INSTRUCTION)
  - Encours crédit + Épargne totale (collecte + classique)
  - Avalistes en attente (AvalisteConsent PENDING)
  - Campagnes validations (LoanRequest EN_VALIDATION_CAMPAGNE)
  - Campagnes micro-crédit actives
  - Prêteurs actifs + tranches DISPONIBLE/ENGAGEE
  - Funding en cours (LoanFundingRequest PENDING/REALLOCATING)
  - Cycle anniversaire épargne (notifié/urgence/en_attente_paiement)
  - Crédits en retard / contentieux
  - Escalades judiciaires ouvertes

Membres créés (suffixés `.demo` pour ne pas écraser les comptes existants) :

  ben.demo@gathe.test          actif ancien BRC validé (peut être avaliste, prêteur)
  fatou.demo@gathe.test        actif ancien sans BRC (prêteur Mode B)
  alex.demo@gathe.test         actif ancien sans BRC (a accepté un mandat avaliste)
  rita.demo@gathe.test         nouveau membre (1 mois) → demande crédit voie AVALISTE
  oscar.demo@gathe.test        membre TEMPORAIRE (issu d'une campagne)
  sam.demo@gathe.test          actif avec crédit en retard
  diane.demo@gathe.test        actif avec crédit contentieux + escalade en cours
  lucia.demo@gathe.test        actif avec compte épargne classique cycle URGENCE
  zoe.demo@gathe.test          actif avec compte épargne classique EN_ATTENTE_PAIEMENT
  paul.demo@gathe.test         suspendu

Mot de passe pour tous : ``test1234``
"""
from __future__ import annotations

import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps_coop.loans.avaliste_services import request_avaliste_consent
from apps_coop.loans.funding_services import request_funding
from apps_coop.loans.models import (
    JudicialEscalation,
    Loan,
    LoanInstallment,
    LoanRequest,
    MicrocreditCampaign,
)
from apps_coop.members.models import (
    BRCDocument,
    Member,
    MembershipRequest,
)
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    SavingsAccount,
    SavingsTransaction,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Crée un jeu de données démo pour illustrer tous les KPIs du dashboard 2026."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("→ Seed démo dashboard 2026…"))

        # Clean idempotent : on supprime UNIQUEMENT ce qu'on a créé via ce seed
        # (membres dont l'email se termine en .demo@gathe.test). Les vrais
        # comptes restent intacts.
        self._cleanup_demo_data()

        # 1) Référents : un admin "responsable" pour les FK created_by
        admin = self._get_or_create_admin()

        # 2) Membres ancrés (anciens, divers profils)
        ben = self._make_member(
            "ben.demo@gathe.test",
            "Ben", "Mballa",
            seniority_days=540,
            statut=Member.Statut.ACTIF,
            is_brc=True,
            classic_solde=Decimal("300000"),
            collecte_solde=Decimal("50000"),
        )
        fatou = self._make_member(
            "fatou.demo@gathe.test",
            "Fatou", "Diop",
            seniority_days=450,
            statut=Member.Statut.ACTIF,
            classic_solde=Decimal("250000"),
            collecte_solde=Decimal("30000"),
        )
        alex = self._make_member(
            "alex.demo@gathe.test",
            "Alex", "Ngono",
            seniority_days=400,
            statut=Member.Statut.ACTIF,
            classic_solde=Decimal("150000"),
            collecte_solde=Decimal("20000"),
        )

        # 3) Nouveau membre (1 mois) — demande crédit voie AVALISTE
        rita = self._make_member(
            "rita.demo@gathe.test",
            "Rita", "Kouemo",
            seniority_days=30,
            statut=Member.Statut.ACTIF,
            collecte_solde=Decimal("8000"),
        )

        # 4) Membre TEMPORAIRE issu d'une campagne micro-crédit
        oscar = self._make_member(
            "oscar.demo@gathe.test",
            "Oscar", "Bouba",
            seniority_days=10,
            statut=Member.Statut.TEMPORAIRE,
            collecte_solde=Decimal("0"),
        )

        # 5) Suspendu (pour le KPI "suspendu")
        self._make_member(
            "paul.demo@gathe.test",
            "Paul", "Tchoua",
            seniority_days=60,
            statut=Member.Statut.SUSPENDU,
        )

        # 6) Membre avec crédit en retard
        sam = self._make_member(
            "sam.demo@gathe.test",
            "Sam", "Kana",
            seniority_days=300,
            statut=Member.Statut.ACTIF,
            collecte_solde=Decimal("15000"),
            classic_solde=Decimal("80000"),
        )
        self._make_loan(
            sam, montant=Decimal("200000"), suffix="LATE",
            statut=Loan.Statut.EN_RETARD, days_since_disbursement=120,
        )

        # 7) Membre avec crédit contentieux + escalade EN_INSTANCE
        diane = self._make_member(
            "diane.demo@gathe.test",
            "Diane", "Sah",
            seniority_days=400,
            statut=Member.Statut.ACTIF,
            collecte_solde=Decimal("5000"),
            classic_solde=Decimal("30000"),
        )
        diane_loan = self._make_loan(
            diane, montant=Decimal("300000"), suffix="CONT",
            statut=Loan.Statut.CONTENTIEUX, days_since_disbursement=200,
            poursuite=True,
        )
        JudicialEscalation.objects.create(
            loan=diane_loan,
            statut=JudicialEscalation.Statut.EN_INSTANCE,
            declenche_par=admin,
            declenche_mode="manual",
            motif=(
                "Reliquat impayé après saisie épargne. Mise en demeure restée "
                "sans réponse depuis 60 jours. Demande l'ouverture d'une "
                "procédure judiciaire pour engager la saisie des biens."
            ),
        )

        # 8) Membres avec cycles épargne classique en différents états
        lucia = self._make_member(
            "lucia.demo@gathe.test",
            "Lucia", "Etoundi",
            seniority_days=350,
            statut=Member.Statut.ACTIF,
            classic_solde=Decimal("120000"),
            classic_cycle_state=ClassicSavingsAccount.StatutRenouvellement.URGENCE,
            classic_maturity_days_ahead=5,
        )
        zoe = self._make_member(
            "zoe.demo@gathe.test",
            "Zoé", "Foka",
            seniority_days=400,
            statut=Member.Statut.ACTIF,
            classic_solde=Decimal("100000"),
            classic_cycle_state=ClassicSavingsAccount.StatutRenouvellement.EN_ATTENTE_PAIEMENT,
            classic_maturity_days_ahead=-3,
        )
        # 1 membre en NOTIFIE pour avoir aussi cette catégorie
        self._make_member(
            "yann.demo@gathe.test",
            "Yann", "Bell",
            seniority_days=300,
            statut=Member.Statut.ACTIF,
            classic_solde=Decimal("75000"),
            classic_cycle_state=ClassicSavingsAccount.StatutRenouvellement.NOTIFIE,
            classic_maturity_days_ahead=20,
        )

        # 9) Adhésions à instruire (3 demandes en attente)
        for nom, prenom, email in [
            ("Nguemo", "Pierre", "pierre.nguemo.demo@adh.test"),
            ("Tchamba", "Aline", "aline.tchamba.demo@adh.test"),
            ("Bouba", "Cécile", "cecile.bouba.demo@adh.test"),
        ]:
            MembershipRequest.objects.create(
                email=email,
                nom=nom,
                prenom=prenom,
                city="Douala",
                phone="+237699000000",
                motivation=(
                    "Je souhaite rejoindre la coopérative pour construire une "
                    "épargne stable et accéder à des microcrédits adaptés."
                ),
                language="fr",
                statut=MembershipRequest.Statut.EN_ATTENTE,
            )

        # 10) Crédits en instruction (2 LR EN_INSTRUCTION)
        for borrower in (ben, fatou):
            LoanRequest.objects.create(
                member=borrower,
                montant_demande=Decimal("400000"),
                duree_mois=12,
                motif="Achat équipement professionnel.",
                statut=LoanRequest.Statut.EN_INSTRUCTION,
            )

        # 11) Campagnes micro-crédit (2 actives + 1 fermée) avec flyer PNG
        c_commercants = self._make_campaign(
            admin,
            nom="Campagne commerçants - juin 2026",
            profil_cible="commercants",
            date_debut=date.today() - timedelta(days=5),
            date_fin=date.today() + timedelta(days=25),
            montant_min=Decimal("5000"),
            montant_max=Decimal("50000"),
            taux_interet=Decimal("0.10"),
            nb_jours_recouvrement=60,
            plafond_beneficiaires=50,
            actif=True,
            flyer_palette=(212, 88, 28),  # orange
            flyer_subtitle="Commerçants & marchés",
        )
        # Audience : ben + fatou + alex sont ciblés "comme prospects commerçants"
        c_commercants.targeted_members.set([ben, fatou, alex])

        c_agriculteurs = self._make_campaign(
            admin,
            nom="Campagne agriculteurs - récolte 2026",
            profil_cible="agriculteurs",
            date_debut=date.today() - timedelta(days=10),
            date_fin=date.today() + timedelta(days=45),
            montant_min=Decimal("10000"),
            montant_max=Decimal("100000"),
            taux_interet=Decimal("0.08"),
            nb_jours_recouvrement=90,
            plafond_beneficiaires=30,
            actif=True,
            flyer_palette=(58, 128, 64),  # vert agricole
            flyer_subtitle="Récolte saisonnière",
        )
        c_agriculteurs.targeted_members.set([sam, diane])

        self._make_campaign(
            admin,
            nom="Campagne parents - rentrée 2025",
            profil_cible="parents",
            date_debut=date.today() - timedelta(days=120),
            date_fin=date.today() - timedelta(days=30),
            montant_min=Decimal("5000"),
            montant_max=Decimal("30000"),
            taux_interet=Decimal("0.10"),
            nb_jours_recouvrement=60,
            actif=False,
            closed_at=timezone.now() - timedelta(days=30),
            close_reason="expired",
            flyer_palette=(120, 80, 180),  # violet
            flyer_subtitle="Rentrée scolaire 2025",
        )

        # 12) LR EN_VALIDATION_CAMPAGNE (oscar TEMPORAIRE désigné par la campagne commerçants)
        # Rattacher oscar à la campagne (Member.microcampaign)
        oscar.microcampaign = c_commercants
        oscar.save(update_fields=["microcampaign"])
        LoanRequest.objects.create(
            member=oscar,
            montant_demande=Decimal("25000"),
            duree_mois=6,
            motif="Stock boutique - rentrée scolaire.",
            statut=LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
            microcampaign=c_commercants,
        )

        # 13) Avaliste consent PENDING : rita demande, alex est avaliste désigné
        rita_lr = LoanRequest.objects.create(
            member=rita,
            montant_demande=Decimal("80000"),
            duree_mois=6,
            motif="Investissement matériel petit commerce.",
            statut=LoanRequest.Statut.EN_INSTRUCTION,
        )
        # Pose le consent PENDING en passant par le service (gère snapshot soldes + statut LR)
        try:
            request_avaliste_consent(
                rita_lr,
                numero_identification=alex.numero_membre,
                nom=alex.nom,
            )
        except ValueError as exc:
            self.stdout.write(self.style.WARNING(f"  ⚠ avaliste consent skipped: {exc}"))

        # 14) Convention prêteur + tranches + funding en cours
        # Ben et Fatou prêtent ; Sam emprunte (nouveau crédit pour le funding)
        try:
            opt_in_lender(member=ben, is_global=False, actor=admin)
            add_tranche(member=ben, montant=Decimal("100000"))
            add_tranche(member=ben, montant=Decimal("50000"))
        except ValueError as exc:
            self.stdout.write(self.style.WARNING(f"  ⚠ ben lender opt-in skipped: {exc}"))

        try:
            opt_in_lender(member=fatou, is_global=True, actor=admin)
        except ValueError as exc:
            self.stdout.write(self.style.WARNING(f"  ⚠ fatou lender opt-in skipped: {exc}"))

        # Crée un Loan ACTIF pour Ben/Fatou pour qui un funding sera lancé
        funding_borrower = self._make_member(
            "borrower.demo@gathe.test",
            "Borrower", "Demo",
            seniority_days=400,
            statut=Member.Statut.ACTIF,
            collecte_solde=Decimal("20000"),
        )
        funding_lr = LoanRequest.objects.create(
            member=funding_borrower,
            montant_demande=Decimal("80000"),
            duree_mois=12,
            motif="Test funding 24h - dashboard demo.",
            statut=LoanRequest.Statut.APPROUVEE,
            date_decision=timezone.now() - timedelta(hours=2),
        )
        funding_loan = Loan.objects.create(
            member=funding_borrower,
            loan_request=funding_lr,
            numero_dossier="GF-CR-DEMO-FUND",
            montant=Decimal("80000"),
            taux_interet=Decimal("0.10"),
            duree_mois=12,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal("88000"),
            solde_restant=Decimal("88000"),
            statut=Loan.Statut.ACTIF,
        )
        try:
            request_funding(funding_loan, actor=admin)
        except Exception as exc:  # noqa: BLE001 — best-effort si pas assez de prêteurs
            self.stdout.write(self.style.WARNING(f"  ⚠ funding request skipped: {exc}"))

        # 15) BRC documents — avec de vrais fichiers PNG pour preview admin
        self._make_brc_document(
            member=ben,
            statut=BRCDocument.Statut.VALIDE,
            valider=admin,
            valide_at=timezone.now() - timedelta(days=30),
            stamp="VALIDÉ",
            stamp_color=(34, 139, 34),
        )
        self._make_brc_document(
            member=lucia,
            statut=BRCDocument.Statut.EN_ATTENTE,
            stamp="EN ATTENTE",
            stamp_color=(218, 165, 32),
        )
        # Un BRC rejeté pour illustrer le filtre "Rejetés" + le motif
        self._make_brc_document(
            member=fatou,
            statut=BRCDocument.Statut.REJETE,
            stamp="REJETÉ",
            stamp_color=(178, 34, 34),
            motif_rejet=(
                "Document illisible — la 2e page n'a pas été scannée. Merci "
                "de re-uploader le justificatif complet (recto + verso)."
            ),
        )

        self.stdout.write(self.style.SUCCESS("✓ Seed démo terminé."))
        self._print_summary()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_demo_data(self):
        """Supprime UNIQUEMENT les données démo précédentes (.demo dans email)."""
        # Demandes d'adhésion démo
        MembershipRequest.objects.filter(email__contains=".demo@adh.test").delete()
        # Membres démo + cascade (loans, savings, tranches, etc.)
        demo_users = User.objects.filter(email__contains=".demo@gathe.test")
        # Suppression manuelle des Loans (PROTECT) avant le User
        for u in demo_users:
            member = getattr(u, "member", None)
            if member is None:
                continue
            # Cascade par dépendance descendante
            for loan in Loan.objects.filter(member=member):
                JudicialEscalation.objects.filter(loan=loan).delete()
                LoanInstallment.objects.filter(loan=loan).delete()
                # Funding requests (cascade via OneToOneField + CASCADE/PROTECT)
                from apps_coop.loans.models import LoanFundingRequest
                LoanFundingRequest.objects.filter(loan=loan).delete()
                loan.delete()
            # AvalisteConsent peut référencer ce member soit en tant que
            # demandeur (via loan_request.member) soit en tant qu'avaliste (FK
            # PROTECT). On nettoie les deux côtés avant de toucher au membre.
            from apps_coop.loans.models import AvalisteConsent, LenderConsentRequest
            AvalisteConsent.objects.filter(avaliste=member).delete()
            AvalisteConsent.objects.filter(loan_request__member=member).delete()
            # LenderConsentRequest pointe le lender en PROTECT.
            LenderConsentRequest.objects.filter(lender=member).delete()
            LoanRequest.objects.filter(member=member).delete()
            BRCDocument.objects.filter(member=member).delete()
            # Lender tranches doivent être supprimées avant le member (PROTECT)
            from apps_coop.savings.models import LenderConsent, LenderTranche
            LenderTranche.objects.filter(member=member).delete()
            LenderConsent.objects.filter(member=member).delete()
            ClassicSavingsAccount.objects.filter(member=member).delete()
            SavingsTransaction.objects.filter(account__member=member).delete()
            SavingsAccount.objects.filter(member=member).delete()
            member.delete()
        demo_users.delete()
        # Campagnes démo (par nom préfixe)
        MicrocreditCampaign.objects.filter(nom__icontains="Campagne ").delete()

    # ------------------------------------------------------------------
    # Helpers : create user + member with savings
    # ------------------------------------------------------------------

    def _get_or_create_admin(self):
        admin, created = User.objects.get_or_create(
            username="admin@gathe.test",
            defaults={
                "email": "admin@gathe.test",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            admin.set_password("test1234")
            admin.save()
        return admin

    def _make_member(
        self,
        email: str,
        prenom: str,
        nom: str,
        *,
        seniority_days: int,
        statut: str,
        is_brc: bool = False,
        collecte_solde: Decimal = Decimal("0"),
        classic_solde: Decimal = Decimal("0"),
        classic_cycle_state: str | None = None,
        classic_maturity_days_ahead: int | None = None,
    ) -> Member:
        user = self._ensure_user(email, password="test1234", first_name=prenom, last_name=nom)
        member_group, _ = Group.objects.get_or_create(name="member")
        user.groups.add(member_group)

        # Numéro de membre basé sur l'email (stable, unique)
        numero = f"GF-DEMO-{abs(hash(email)) % 9999:04d}"
        member, _ = Member.objects.get_or_create(
            user=user,
            defaults={
                "numero_membre": numero,
                "nom": nom,
                "prenom": prenom,
                "phone": "+237699111000",
                "statut": statut,
                "date_adhesion": date.today() - timedelta(days=seniority_days),
                "is_brc_member": is_brc,
            },
        )
        # Re-sync mutables
        member.numero_membre = numero
        member.statut = statut
        member.nom = nom
        member.prenom = prenom
        member.date_adhesion = date.today() - timedelta(days=seniority_days)
        member.is_brc_member = is_brc
        member.save()

        # Compte collecte (auto-créé par signal en général, mais on garantit ici)
        savings, _ = SavingsAccount.objects.get_or_create(
            member=member,
            defaults={
                "solde": Decimal("0"),
                "date_ouverture": member.date_adhesion,
                "taux_interet_applique": Decimal("0.0350"),
            },
        )
        if collecte_solde > 0:
            savings.solde = collecte_solde
            savings.save(update_fields=["solde"])

        # Épargne classique optionnelle
        if classic_solde > 0 or classic_cycle_state:
            classic, _ = ClassicSavingsAccount.objects.get_or_create(
                member=member,
                defaults={
                    "solde": classic_solde,
                    "date_ouverture": date.today() - timedelta(days=min(seniority_days, 360)),
                },
            )
            classic.solde = classic_solde
            if classic_cycle_state:
                classic.statut_renouvellement = classic_cycle_state
            if classic_maturity_days_ahead is not None:
                classic.date_prochaine_maturite = date.today() + timedelta(
                    days=classic_maturity_days_ahead
                )
            classic.save()

        return member

    def _make_loan(
        self,
        member: Member,
        *,
        montant: Decimal,
        suffix: str,
        statut: str,
        days_since_disbursement: int,
        poursuite: bool = False,
    ) -> Loan:
        lr = LoanRequest.objects.create(
            member=member,
            montant_demande=montant,
            duree_mois=12,
            motif="Crédit démo dashboard.",
            statut=LoanRequest.Statut.APPROUVEE,
            date_decision=timezone.now() - timedelta(days=days_since_disbursement + 5),
        )
        total = montant * Decimal("1.12")
        loan = Loan.objects.create(
            member=member,
            loan_request=lr,
            numero_dossier=f"GF-CR-DEMO-{suffix}",
            montant=montant,
            taux_interet=Decimal("0.12"),
            taux_penalite=Decimal("0.50"),
            duree_mois=12,
            date_decaissement=date.today() - timedelta(days=days_since_disbursement),
            date_premiere_echeance=date.today() - timedelta(days=days_since_disbursement - 30),
            montant_total_du=total,
            solde_restant=total * Decimal("0.6"),  # 60% restant
            statut=statut,
        )
        if poursuite:
            loan.epargne_saisie_at = timezone.now() - timedelta(days=60)
            loan.epargne_saisie_montant = montant * Decimal("0.3")
            loan.poursuite_judiciaire_at = timezone.now() - timedelta(days=70)
            loan.save(
                update_fields=[
                    "epargne_saisie_at",
                    "epargne_saisie_montant",
                    "poursuite_judiciaire_at",
                ]
            )
        return loan

    def _make_campaign(
        self,
        admin,
        *,
        nom: str,
        profil_cible: str,
        date_debut,
        date_fin,
        montant_min: Decimal,
        montant_max: Decimal,
        taux_interet: Decimal,
        nb_jours_recouvrement: int,
        plafond_beneficiaires: int | None = None,
        actif: bool = True,
        closed_at=None,
        close_reason: str = "",
        flyer_palette: tuple[int, int, int] = (30, 64, 124),
        flyer_subtitle: str = "",
    ) -> MicrocreditCampaign:
        """Crée une MicrocreditCampaign avec un VRAI flyer PNG joint.

        Le flyer rend visuellement plus tangible la campagne dans l'admin
        et permet de tester la preview (thumbnail + modal plein écran).
        """
        c = MicrocreditCampaign.objects.create(
            nom=nom,
            profil_cible=profil_cible,
            date_debut=date_debut,
            date_fin=date_fin,
            montant_min=montant_min,
            montant_max=montant_max,
            taux_interet=taux_interet,
            nb_jours_recouvrement=nb_jours_recouvrement,
            plafond_beneficiaires=plafond_beneficiaires,
            actif=actif,
            closed_at=closed_at,
            close_reason=close_reason,
            created_by=admin,
        )
        png_bytes = self._generate_flyer_png(
            title=nom,
            profil_cible=profil_cible,
            montant_max=montant_max,
            taux_interet=taux_interet,
            palette=flyer_palette,
            subtitle=flyer_subtitle,
        )
        filename = f"flyer_{profil_cible.lower()}_{c.id}.png"
        c.flyer.save(filename, ContentFile(png_bytes), save=True)
        return c

    def _generate_flyer_png(
        self,
        *,
        title: str,
        profil_cible: str,
        montant_max: Decimal,
        taux_interet: Decimal,
        palette: tuple[int, int, int],
        subtitle: str,
    ) -> bytes:
        """Génère un flyer PNG portait (800×1200) façon affiche promotionnelle."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            # Fallback minimal (cf. _generate_brc_png)
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        W, H = 800, 1200
        img = Image.new("RGB", (W, H), color=palette)
        draw = ImageDraw.Draw(img)

        try:
            hero = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
            big = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
            mid = ImageFont.truetype("DejaVuSans.ttf", 26)
            small = ImageFont.truetype("DejaVuSans.ttf", 20)
            tag = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        except OSError:
            hero = ImageFont.load_default()
            big = ImageFont.load_default()
            mid = ImageFont.load_default()
            small = ImageFont.load_default()
            tag = ImageFont.load_default()

        # Bandeau "GATHE Finance" en haut
        draw.rectangle([(0, 0), (W, 90)], fill=(20, 20, 30))
        draw.text((40, 28), "GATHE FINANCE", fill=(255, 255, 255), font=big)
        draw.text((W - 200, 38), "Coopérative", fill=(255, 255, 255, 200), font=small)

        # Hero — accroche
        draw.text((40, 160), "Micro-crédit", fill=(255, 255, 255), font=hero)
        draw.text((40, 230), profil_cible.upper(), fill=(255, 255, 255), font=hero)
        if subtitle:
            draw.text((40, 310), subtitle, fill=(255, 255, 255, 230), font=mid)

        # Carte "offre" sur fond clair
        card_y = 420
        card_h = 460
        draw.rectangle([(40, card_y), (W - 40, card_y + card_h)], fill=(248, 248, 244))

        # Bordure colorée à gauche
        draw.rectangle([(40, card_y), (52, card_y + card_h)], fill=palette)

        draw.text((80, card_y + 30), "JUSQU'À", fill=(120, 120, 120), font=small)
        amount_label = f"{int(montant_max):,}".replace(",", " ") + " XAF"
        draw.text((80, card_y + 60), amount_label, fill=palette, font=hero)

        draw.text((80, card_y + 150), f"Taux fixe : {int(taux_interet * 100)} %", fill=(40, 40, 40), font=big)
        draw.text((80, card_y + 210), "Recouvrement quotidien", fill=(80, 80, 80), font=mid)
        draw.text((80, card_y + 244), "Pas de garantie épargne demandée", fill=(80, 80, 80), font=mid)
        draw.text((80, card_y + 278), "Réponse comité sous 7 jours", fill=(80, 80, 80), font=mid)

        # Tag profil cible
        draw.rectangle([(80, card_y + 340), (260, card_y + 380)], fill=palette)
        draw.text((92, card_y + 348), f"#{profil_cible}", fill=(255, 255, 255), font=tag)

        # Footer — CTA
        draw.rectangle([(0, H - 110), (W, H)], fill=(20, 20, 30))
        draw.text(
            (40, H - 90),
            "Renseignements : agence Akwa Bercy",
            fill=(255, 255, 255),
            font=mid,
        )
        draw.text(
            (40, H - 55),
            "ou sur https://gathe-finance.cm",
            fill=(255, 255, 255, 210),
            font=small,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _make_brc_document(
        self,
        *,
        member: Member,
        statut: str,
        stamp: str,
        stamp_color: tuple[int, int, int],
        valider=None,
        valide_at=None,
        motif_rejet: str = "",
    ) -> BRCDocument:
        """Crée un BRCDocument avec un VRAI fichier PNG en pièce jointe.

        La PNG porte le numéro de membre + un tampon visible (« VALIDÉ »,
        « EN ATTENTE », « REJETÉ »). Permet une preview inline immédiate
        dans l'admin sans dépendance à un PDF reader.
        """
        png_bytes = self._generate_brc_png(
            member_label=f"{member.prenom} {member.nom} · {member.numero_membre}",
            stamp=stamp,
            stamp_color=stamp_color,
        )
        filename = f"brc_{member.numero_membre.lower()}_{stamp.replace(' ', '_').lower()}.png"
        doc = BRCDocument.objects.create(
            member=member,
            nom_original=filename,
            taille=len(png_bytes),
            statut=statut,
            motif_rejet=motif_rejet,
        )
        if valider:
            doc.validated_by = valider
            doc.validated_at = valide_at or timezone.now()
            doc.save(update_fields=["validated_by", "validated_at"])
        doc.fichier.save(filename, ContentFile(png_bytes), save=True)
        return doc

    def _generate_brc_png(
        self,
        *,
        member_label: str,
        stamp: str,
        stamp_color: tuple[int, int, int],
    ) -> bytes:
        """Génère une PNG simulant un justificatif (logo + nom + tampon)."""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            # Fallback : on retourne un petit PNG fixe si Pillow indispo
            # (1x1 pixel transparent — ne devrait jamais arriver, Wagtail
            # déjà installé l'utilise).
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )

        W, H = 800, 1100
        img = Image.new("RGB", (W, H), color=(248, 248, 244))
        draw = ImageDraw.Draw(img)

        # Police par défaut (pas besoin de TTF spécifique)
        try:
            big = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
            mid = ImageFont.truetype("DejaVuSans.ttf", 22)
            small = ImageFont.truetype("DejaVuSans.ttf", 16)
            stamp_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
        except OSError:
            big = ImageFont.load_default()
            mid = ImageFont.load_default()
            small = ImageFont.load_default()
            stamp_font = ImageFont.load_default()

        # Bandeau header bleu institutionnel
        draw.rectangle([(0, 0), (W, 90)], fill=(30, 64, 124))
        draw.text((40, 28), "BRC — Broad Range Consulting", fill=(255, 255, 255), font=big)

        # Cadre principal
        draw.rectangle([(40, 130), (W - 40, H - 60)], outline=(120, 120, 120), width=2)
        draw.text((70, 160), "ATTESTATION DE CLIENT", fill=(40, 40, 40), font=big)
        draw.text(
            (70, 220),
            "Le présent document atteste que la personne mentionnée",
            fill=(60, 60, 60),
            font=mid,
        )
        draw.text(
            (70, 250),
            "ci-dessous est cliente du cabinet BRC pour ses obligations",
            fill=(60, 60, 60),
            font=mid,
        )
        draw.text(
            (70, 280),
            "fiscales et comptables.",
            fill=(60, 60, 60),
            font=mid,
        )

        # Bloc identité du membre
        draw.rectangle([(70, 360), (W - 70, 460)], fill=(238, 238, 232))
        draw.text((90, 380), "MEMBRE COOPÉRATIVE", fill=(120, 120, 120), font=small)
        draw.text((90, 410), member_label, fill=(20, 20, 20), font=mid)

        # Quelques lignes de "contenu" pour l'illusion d'un document
        for i, line in enumerate(
            [
                "Date d'émission : 12 mars 2026",
                "Numéro dossier  : BRC-2026-00481",
                "Validité          : 12 mois",
                "Conseil référent : Maître ESSOMBA Patrick",
            ]
        ):
            draw.text((90, 510 + i * 34), line, fill=(50, 50, 50), font=mid)

        # Tampon coloré incliné (simulation simple : un rectangle + texte)
        stamp_w, stamp_h = 360, 90
        stamp_x, stamp_y = W - stamp_w - 80, H - 240
        # Encadré
        draw.rectangle(
            [(stamp_x, stamp_y), (stamp_x + stamp_w, stamp_y + stamp_h)],
            outline=stamp_color,
            width=4,
        )
        # Texte tampon centré
        bbox = draw.textbbox((0, 0), stamp, font=stamp_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (stamp_x + (stamp_w - tw) // 2, stamp_y + (stamp_h - th) // 2 - 4),
            stamp,
            fill=stamp_color,
            font=stamp_font,
        )

        # Signature simulée
        draw.line([(80, H - 130), (350, H - 130)], fill=(100, 100, 100), width=1)
        draw.text((80, H - 120), "Signature du conseiller BRC", fill=(140, 140, 140), font=small)

        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    def _ensure_user(
        self,
        email: str,
        *,
        password: str,
        first_name: str,
        last_name: str,
    ):
        user, _ = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )
        user.set_password(password)
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = True
        user.save()
        return user

    def _print_summary(self):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Compte admin recommandé"))
        self.stdout.write(
            "  admin@gathe.test / test1234  →  http://localhost:3202/login"
        )
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("KPIs dashboard à observer"))
        for line in [
            "Bloc Général",
            "  • Membres actifs ≥ 7  (et 1 suspendu, 1 temporaire)",
            "  • Adhésions à instruire = 3",
            "  • Crédits en instruction = 3 (ben, fatou, rita-via-avaliste)",
            "  • Encours crédit ≈ 660k XAF · Épargne totale ≈ 1.2M XAF",
            "",
            "Bloc Éligibilité 3 voies & prêteurs (refonte 2026)",
            "  • Avalistes en attente = 1 (rita → alex)",
            "  • Campagnes validations = 1 (oscar EN_VALIDATION_CAMPAGNE)",
            "  • Campagnes actives = 2 (commerçants, agriculteurs)",
            "  • Prêteurs actifs = 2 (ben mode B, fatou mode A)",
            "  • Funding en cours = 1 (GF-CR-DEMO-FUND)",
            "",
            "Bloc Épargne & cycles",
            "  • Cycle anniversaire : 1 notifié (yann), 1 urgence (lucia), 1 en_attente_paiement (zoé)",
            "  • BRC validés = 1 (ben)",
            "",
            "Bloc Risque & contentieux",
            "  • Crédits en retard = 1 (sam, GF-CR-DEMO-LATE)",
            "  • Crédits contentieux = 1 (diane, GF-CR-DEMO-CONT)",
            "  • Escalades judiciaires ouvertes = 1 (diane, EN_INSTANCE)",
        ]:
            self.stdout.write(line)
        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                "Tous les comptes démo : mot de passe = test1234 — login portail sur :3201/connexion"
            )
        )
