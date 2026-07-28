"""LOT D — le gel affiché est scindé par MOTIF sur le snapshot épargne classique.

Règle produit : un montant gelé n'est mobilisable pour rembourser un crédit que
si son motif EST ce crédit (apport du demandeur). La caution donnée en tant
qu'avaliste sur le crédit d'un AUTRE membre n'est PAS mobilisable (libérée à la
clôture du crédit garanti). Le serializer doit donc exposer les deux poches
séparément — sinon l'UI mélange « mobilisable » et « non mobilisable ».
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps_coop.loans.models import AvalisteConsent, LoanRequest
from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.savings.serializers import ClassicSavingsAccountReadSerializer
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _classic(member, solde):
    return ClassicSavingsAccount.objects.create(
        member=member, solde=Decimal(solde), date_ouverture=date.today()
    )


def test_gel_split_apport_vs_avaliste():
    """Un membre à la fois DEMANDEUR (apport gelé) et AVALISTE (caution) voit
    les deux poches distinctes ; leur somme = montant_gele_credit."""
    member = MemberFactory()
    account = _classic(member, "200000")

    # Apport gelé sur SON PROPRE crédit → mobilisable.
    LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=6,
        motif="mon credit",
        statut=LoanRequest.Statut.APPROUVEE,
        montant_gele_demandeur=Decimal("10000"),
    )

    # Caution acceptée sur le crédit d'un AUTRE membre → NON mobilisable.
    borrower = MemberFactory(nom="EMPRUNTEUR")
    borrower_lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="credit garanti",
        statut=LoanRequest.Statut.EN_ATTENTE_AVALISTE,
    )
    AvalisteConsent.objects.create(
        loan_request=borrower_lr,
        avaliste=member,
        statut=AvalisteConsent.Statut.ACCEPTED,
        epargne_borrower_at_request=Decimal("0"),
        epargne_avaliste_at_request=Decimal("200000"),
        couverture_ratio=Decimal("1.0"),
        montant_caution=Decimal("15000"),
        identification_numero_saisi=member.numero_membre,
        identification_nom_saisi=member.nom,
    )

    data = ClassicSavingsAccountReadSerializer(account).data

    assert Decimal(data["montant_gele_apport"]) == Decimal("10000")
    assert Decimal(data["montant_gele_avaliste"]) == Decimal("15000")
    assert Decimal(data["montant_gele_credit"]) == Decimal("25000")


def test_gel_split_zero_when_no_engagement():
    member = MemberFactory()
    account = _classic(member, "50000")
    data = ClassicSavingsAccountReadSerializer(account).data
    assert Decimal(data["montant_gele_apport"]) == Decimal("0")
    assert Decimal(data["montant_gele_avaliste"]) == Decimal("0")
    assert Decimal(data["montant_gele_credit"]) == Decimal("0")
    # Sanity : les nouveaux champs sont bien présents dans la sortie.
    assert "montant_gele_apport" in data
    assert "montant_gele_avaliste" in data
