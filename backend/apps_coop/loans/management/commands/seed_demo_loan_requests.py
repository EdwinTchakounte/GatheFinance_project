"""Seed de demandes de credit (LoanRequest) dans plusieurs etats pour
tester le pipeline admin /loan-requests.

Run : python manage.py seed_demo_loan_requests

Idempotent : skip si une LoanRequest existe deja pour ce membre.

Cree 5 LoanRequests sur des membres existants :
    Jean Kamga       . EN_ATTENTE          (frais a payer cote membre)
    Nadine Fotso     . EN_INSTRUCTION      (en attente decision comite)
    Eric Muna        . APPROUVEE_PROVISOIRE (CH-6 . visite terrain a faire)
    Claire Ndongo    . EN_VALIDATION_CAMPAGNE (voie 3 micro-credit)
    David Nyamsi     . REJETEE             (motif renseigne)

Si un compte n'existe pas, la commande tente seed_test_accounts +
seed_demo_credits avant. Si toujours absent, on skip ce membre.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps_coop.loans.models import LoanRequest
from apps_coop.members.models import Member

User = get_user_model()


SEED_REQUESTS = [
    {
        "email": "jean.kamga@test.local",
        "statut": LoanRequest.Statut.EN_ATTENTE,
        "montant": Decimal("80000"),
        "duree_mois": 6,
        "motif": "Achat de marchandise pour la boutique.",
        "extra": {},
    },
    {
        "email": "nadine.fotso@test.local",
        "statut": LoanRequest.Statut.EN_INSTRUCTION,
        "montant": Decimal("150000"),
        "duree_mois": 12,
        "motif": "Investissement dans une machine a coudre industrielle.",
        "extra": {"frais_demande_credit_paye": True},
    },
    {
        "email": "eric.muna@test.local",
        "statut": LoanRequest.Statut.APPROUVEE_PROVISOIRE,
        "montant": Decimal("200000"),
        "duree_mois": 12,
        "motif": "Demarrage activite de transport de marchandise.",
        "extra": {
            "frais_demande_credit_paye": True,
            "date_decision_provisoire": date.today() - timedelta(days=2),
        },
    },
    {
        "email": "claire.ndongo@test.local",
        "statut": LoanRequest.Statut.EN_VALIDATION_CAMPAGNE,
        "montant": Decimal("100000"),
        "duree_mois": 12,
        "motif": "Reapprovisionnement stock saison scolaire (campagne).",
        "extra": {"frais_demande_credit_paye": True},
    },
    {
        "email": "david.nyamsi@test.local",
        "statut": LoanRequest.Statut.REJETEE,
        "montant": Decimal("500000"),
        "duree_mois": 24,
        "motif": "Achat de vehicule personnel.",
        "extra": {
            "frais_demande_credit_paye": True,
            "motif_rejet": "Montant superieur au palier autorise pour ce membre. Voir Article 8.",
            "date_decision": date.today() - timedelta(days=5),
        },
    },
]


class Command(BaseCommand):
    help = "Cree 5 LoanRequest demo dans des etats varies pour tester l'admin."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seed loan-requests demo"))
        self.stdout.write("-" * 72)

        created = skipped = missing = 0

        for spec in SEED_REQUESTS:
            try:
                member = Member.objects.select_related("user").get(
                    user__email=spec["email"],
                )
            except Member.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  - SKIP {spec['email']} . membre absent "
                    "(lance d'abord seed_test_accounts + seed_demo_credits)"
                ))
                missing += 1
                continue

            if LoanRequest.objects.filter(member=member).exists():
                self.stdout.write(
                    f"  - SKIP {member.numero_membre} . loan_request existant"
                )
                skipped += 1
                continue

            extra = dict(spec["extra"])
            motif_rejet = extra.pop("motif_rejet", "")
            date_decision_provisoire = extra.pop("date_decision_provisoire", None)
            date_decision = extra.pop("date_decision", None)
            frais_paye = extra.pop("frais_demande_credit_paye", False)

            req = LoanRequest.objects.create(
                member=member,
                montant_demande=spec["montant"],
                duree_mois=spec["duree_mois"],
                motif=spec["motif"],
                statut=spec["statut"],
                motif_rejet=motif_rejet,
                date_decision_provisoire=date_decision_provisoire,
                date_decision=date_decision,
                frais_demande_credit_paye=frais_paye,
                **extra,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  + {member.numero_membre} . {req.statut} . {spec['montant']} XAF"
            ))
            created += 1

        self.stdout.write("-" * 72)
        self.stdout.write(self.style.SUCCESS(
            f"Done. crees={created} existants={skipped} membres-absents={missing}"
        ))
