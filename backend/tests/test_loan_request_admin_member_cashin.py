"""Admin /loan-requests : expose `member` + cash-in frais d'etude debloque.

Garantit le contrat de 2 changements deployes en juin 2026 pour debloquer
le workflow admin quand une demande de credit reste en `en_attente` faute
de paiement Tara (membre paie en espece a l'agence) :

1. `LoanRequestReadSerializer.member` expose les champs identifiant le
   membre soumetteur (id, nom, prenom, numero_membre, telephone). Sans
   cela l'admin ne sait pas qui contacter / qui encaisser.

2. POST /api/v1/payments/admin/cash-in/ avec `type=frais_demande_credit`
   fait passer la LoanRequest EN_ATTENTE -> EN_INSTRUCTION (via le hook
   `_hook_loan_request_fees` cote payments.services). C'est ce qui debloque
   les boutons "Approbation provisoire" / "Rejeter" cote dashboard admin.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.loans.models import LoanRequest
from apps_coop.payments.models import Payment


pytestmark = pytest.mark.django_db


@pytest.fixture
def loan_request_en_attente(active_member):
    """Demande de credit qui vient d'etre soumise, frais d'etude pas encore
    regles. C'est l'etat dans lequel l'admin la voit et a besoin du fix."""
    return LoanRequest.objects.create(
        member=active_member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test admin cash-in et serializer member.",
        statut=LoanRequest.Statut.EN_ATTENTE,
    )


class TestAdminLoanRequestSerializerExposesMember:
    """GET /admin/requests/ doit renvoyer l'objet `member` complet."""

    def test_member_object_present_with_all_required_fields(
        self,
        loan_request_en_attente,
        active_member,
        admin_user,
    ):
        client = APIClient()
        client.force_authenticate(admin_user)

        r = client.get("/api/v1/loans/admin/requests/?statut=en_attente")
        assert r.status_code == 200, r.content
        body = r.json()
        assert isinstance(body, list) and len(body) >= 1

        # Trouve la demande creee par le fixture (par id, robuste si autres
        # demandes existent dans la base de test).
        item = next(
            (x for x in body if x["id"] == loan_request_en_attente.id),
            None,
        )
        assert item is not None, "LoanRequest fixture absent de la liste"

        member = item.get("member")
        assert member is not None, (
            "Le champ `member` doit etre expose pour le cash-in admin."
        )
        # Contrat strict : ces 5 champs doivent etre presents pour que le
        # frontend admin (CashInModal prefill) fonctionne sans backend supplementaire.
        for key in ("id", "numero_membre", "nom", "prenom", "telephone"):
            assert key in member, f"member.{key} manquant"
        assert member["id"] == active_member.id
        assert member["numero_membre"] == active_member.numero_membre
        assert member["nom"] == active_member.nom
        assert member["prenom"] == active_member.prenom
        # Le model Django nomme le champ `phone` ; l'API expose `telephone`.
        # On verifie explicitement que la traduction backend est en place
        # (regression : un getattr(m, "telephone") aurait renvoye "").
        assert member["telephone"] == active_member.phone


class TestAdminCashInFraisDemandeCreditMovesToEnInstruction:
    """POST /admin/cash-in/ avec type=frais_demande_credit debloque la demande."""

    def test_cash_in_moves_request_from_en_attente_to_en_instruction(
        self,
        loan_request_en_attente,
        active_member,
        admin_user,
    ):
        # Baseline : la demande est bien EN_ATTENTE avant cash-in.
        loan_request_en_attente.refresh_from_db()
        assert loan_request_en_attente.statut == LoanRequest.Statut.EN_ATTENTE

        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            "/api/v1/payments/admin/cash-in/",
            {
                "member_id": active_member.id,
                "type": "frais_demande_credit",
                "montant": "5000",
                "note": (
                    f"Frais d'etude demande #{loan_request_en_attente.id} "
                    "regles en espece au guichet."
                ),
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        payment_id = r.json()["id"]

        # 1. Le Payment cree est valide direct (source=MANUEL, statut=VALIDE).
        payment = Payment.objects.get(pk=payment_id)
        assert payment.statut == Payment.Statut.VALIDE
        assert payment.type == Payment.Type.FRAIS_DEMANDE_CREDIT
        assert payment.member_id == active_member.id

        # 2. Le hook _hook_loan_request_fees a fait passer la demande
        #    EN_ATTENTE -> EN_INSTRUCTION (= boutons admin s'affichent).
        loan_request_en_attente.refresh_from_db()
        assert (
            loan_request_en_attente.statut
            == LoanRequest.Statut.EN_INSTRUCTION
        ), (
            "Le cash-in des frais d'etude doit debloquer la demande en "
            "EN_INSTRUCTION pour que l'admin puisse decider."
        )

    def test_cash_in_no_op_when_no_pending_request(
        self,
        active_member,
        admin_user,
    ):
        """Si aucune LoanRequest EN_ATTENTE n'existe (cas degenere), le
        cash-in cree le Payment mais ne casse rien."""
        client = APIClient()
        client.force_authenticate(admin_user)
        r = client.post(
            "/api/v1/payments/admin/cash-in/",
            {
                "member_id": active_member.id,
                "type": "frais_demande_credit",
                "montant": "5000",
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        # Aucune LoanRequest ne devrait avoir change de statut (puisqu'il
        # n'y en avait aucune en EN_ATTENTE au depart).
        assert LoanRequest.objects.filter(
            member=active_member,
            statut=LoanRequest.Statut.EN_INSTRUCTION,
        ).count() == 0
