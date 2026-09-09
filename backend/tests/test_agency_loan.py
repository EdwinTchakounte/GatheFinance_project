"""Crédit accordé DIRECTEMENT À L'AGENCE — décision de séance, sans demande en ligne.

Le comité statue parfois en présence du membre, dossier papier en main. Il
n'existe alors aucune demande à instruire dans le système. Ce chemin crée la
``LoanRequest`` (pour garder la trace de la décision) puis l'approuve aussitôt,
en réutilisant ``approve_loan_request``.

Ce que ces tests figent :
  - le crédit produit est IDENTIQUE à celui d'une approbation classique
    (durée au barème, taux figés, échéancier, date butoire, `loan.approved`) ;
  - les garde-fous qui protègent l'argent tiennent (membre actif, pas de
    crédit déjà en cours), ceux qui ne relèvent que de la procédure sautent ;
  - un refus ne laisse AUCUNE demande orpheline derrière lui ;
  - l'origine « agence » reste identifiable après coup.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.loans.services import AgencyLoanError, create_agency_loan
from apps_coop.members.models import Member
from apps_coop.payments.models import RateParam
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/loans/admin/manual/"
_ECHEANCE = date.today() + timedelta(days=30)


def _comite_superuser():
    """Superuser : franchit à la fois le middleware RBAC et `IsComite`."""
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m.user


def _comite_staff():
    """Staff « legacy » (sans rôle RBAC) + groupe comité."""
    m = MemberFactory()
    m.user.is_staff = True
    m.user.save(update_fields=["is_staff"])
    m.user.groups.add(Group.objects.get_or_create(name="comite")[0])
    return m.user


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def _payload(member, **over):
    body = {
        "member_id": member.id,
        "montant": "100000",
        "motif": "Fonds de roulement — décision du comité en séance",
        "date_premiere_echeance": _ECHEANCE.isoformat(),
    }
    body.update(over)
    return body


# --- Le crédit produit est un crédit normal ---------------------------------


class TestCreditProduit:
    def test_cree_un_credit_actif_en_attente_de_decaissement(self):
        member = MemberFactory()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Fonds de roulement", date_premiere_echeance=_ECHEANCE,
        )

        assert loan.statut == Loan.Statut.ACTIF
        # L'argent n'est PAS encore sorti : le décaissement reste un acte à part.
        assert loan.en_attente_decaissement is True
        assert loan.numero_dossier

    def test_duree_deduite_du_bareme_et_non_saisie(self):
        """Art. 7 : 100 000 tombe dans le palier 51 000–200 000 → 3 mois."""
        member = MemberFactory()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Test barème", date_premiere_echeance=_ECHEANCE,
        )

        assert loan.duree_mois == 3

    def test_genere_lecheancier_et_la_date_butoire(self):
        member = MemberFactory()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Test échéancier", date_premiere_echeance=_ECHEANCE,
        )

        echeances = list(loan.installments.order_by("date_echeance"))
        assert len(echeances) > 0
        assert loan.date_butoire == echeances[-1].date_echeance

    def test_taux_par_defaut_pris_au_bareme(self):
        member = MemberFactory()
        RateParam.objects.update_or_create(
            code=RateParam.Code.LOAN_INTEREST,
            defaults={"libelle": "Intérêt", "valeur": Decimal("0.10"), "actif": True},
        )

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Taux barème", date_premiere_echeance=_ECHEANCE,
        )

        assert loan.taux_interet == Decimal("0.10")

    def test_taux_explicite_respecte(self):
        member = MemberFactory()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"), motif="Taux forcé",
            date_premiere_echeance=_ECHEANCE, taux_annuel=Decimal("0.05"),
        )

        assert loan.taux_interet == Decimal("0.05")

    def test_la_demande_creee_est_approuvee_et_marquee_agence(self):
        member = MemberFactory()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Trace de séance", date_premiere_echeance=_ECHEANCE,
            note="Dossier papier n°12",
        )

        req = loan.loan_request
        assert req.statut == LoanRequest.Statut.APPROUVEE
        # Repère durable de l'origine : sans lui, impossible de distinguer plus
        # tard un dossier instruit en ligne d'une décision de guichet.
        assert req.extra_payload.get("octroye_en_agence") is True
        assert req.extra_payload.get("note_agence") == "Dossier papier n°12"
        # Les frais d'étude sont réputés réglés au guichet, sinon la demande
        # resterait bloquée à la porte de l'instruction.
        assert req.frais_demande_credit_paye is True


# --- Les garde-fous qui protègent l'argent ----------------------------------


class TestGardeFous:
    def test_membre_non_actif_refuse(self):
        member = MemberFactory()
        member.statut = Member.Statut.SUSPENDU
        member.save(update_fields=["statut"])

        with pytest.raises(AgencyLoanError, match="actif"):
            create_agency_loan(
                member=member, montant=Decimal("100000"),
                motif="Test", date_premiere_echeance=_ECHEANCE,
            )

    def test_credit_deja_en_cours_refuse(self):
        """§14.6 — deux crédits en parallèle doublent l'exposition."""
        member = MemberFactory()
        create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Premier", date_premiere_echeance=_ECHEANCE,
        )

        with pytest.raises(AgencyLoanError, match="déjà"):
            create_agency_loan(
                member=member, montant=Decimal("100000"),
                motif="Second", date_premiere_echeance=_ECHEANCE,
            )

    def test_montant_sous_le_palier_minimum_refuse(self):
        member = MemberFactory()
        with pytest.raises(AgencyLoanError):
            create_agency_loan(
                member=member, montant=Decimal("100"),
                motif="Trop petit", date_premiere_echeance=_ECHEANCE,
            )

    def test_un_refus_ne_laisse_aucune_demande_orpheline(self):
        """Le barème est vérifié AVANT toute écriture."""
        member = MemberFactory()

        with pytest.raises(AgencyLoanError):
            create_agency_loan(
                member=member, montant=Decimal("100"),
                motif="Trop petit", date_premiere_echeance=_ECHEANCE,
            )

        assert not LoanRequest.objects.filter(member=member).exists()

    def test_montant_nul_ou_negatif_refuse(self):
        member = MemberFactory()
        for mauvais in (Decimal("0"), Decimal("-5000")):
            with pytest.raises(AgencyLoanError, match="positif"):
                create_agency_loan(
                    member=member, montant=mauvais,
                    motif="Test", date_premiere_echeance=_ECHEANCE,
                )

    def test_motif_obligatoire(self):
        """Sans motif, aucune trace de ce qui a été décidé."""
        member = MemberFactory()
        with pytest.raises(AgencyLoanError, match="motif"):
            create_agency_loan(
                member=member, montant=Decimal("100000"),
                motif="   ", date_premiere_echeance=_ECHEANCE,
            )


# --- Traçabilité ------------------------------------------------------------


def test_audit_dedie_a_loctroi_en_agence():
    member = MemberFactory()
    acteur = _comite_superuser()

    loan = create_agency_loan(
        member=member, montant=Decimal("100000"), motif="Séance du 8/09",
        date_premiere_echeance=_ECHEANCE, actor=acteur,
    )

    log = AuditLog.objects.filter(action="loan.created_in_agency").latest("id")
    assert log.entite_id == loan.id
    assert log.details_json["numero_dossier"] == loan.numero_dossier
    assert log.details_json["numero_membre"] == member.numero_membre
    # L'audit d'approbation classique reste écrit lui aussi : on ne perd pas la
    # trace normale sous prétexte que l'origine diffère.
    assert AuditLog.objects.filter(action="loan.approved", entite_id=loan.id).exists()


# --- Endpoint + permissions -------------------------------------------------


class TestEndpoint:
    def test_superuser_peut_octroyer(self):
        member = MemberFactory()

        res = _api(_comite_superuser()).post(URL, _payload(member), format="json")

        assert res.status_code == 201, res.json()
        assert Loan.objects.filter(member=member).exists()

    def test_comite_staff_peut_octroyer(self):
        member = MemberFactory()

        res = _api(_comite_staff()).post(URL, _payload(member), format="json")

        assert res.status_code == 201, res.json()

    def test_staff_hors_comite_refuse(self):
        """Accorder du crédit reste un acte du comité."""
        member = MemberFactory()
        staff = MemberFactory()
        staff.user.is_staff = True
        staff.user.save(update_fields=["is_staff"])

        res = _api(staff.user).post(URL, _payload(member), format="json")

        assert res.status_code == 403
        assert not Loan.objects.filter(member=member).exists()

    def test_membre_simple_refuse(self):
        member = MemberFactory()
        intrus = MemberFactory()

        res = _api(intrus.user).post(URL, _payload(member), format="json")

        assert res.status_code in (401, 403)
        assert not Loan.objects.filter(member=member).exists()

    def test_anonyme_refuse(self):
        member = MemberFactory()
        res = APIClient().post(URL, _payload(member), format="json")
        assert res.status_code in (401, 403)

    def test_membre_introuvable_404(self):
        res = _api(_comite_superuser()).post(
            URL,
            {
                "member_id": 999999,
                "montant": "100000",
                "motif": "Test",
                "date_premiere_echeance": _ECHEANCE.isoformat(),
            },
            format="json",
        )
        assert res.status_code == 404

    def test_membre_inactif_renvoie_400_pas_500(self):
        member = MemberFactory()
        member.statut = Member.Statut.RADIE
        member.save(update_fields=["statut"])

        res = _api(_comite_superuser()).post(URL, _payload(member), format="json")

        assert res.status_code == 400
        assert "actif" in res.json()["detail"]

    def test_montant_hors_bareme_renvoie_400(self):
        member = MemberFactory()
        res = _api(_comite_superuser()).post(
            URL, _payload(member, montant="100"), format="json",
        )
        assert res.status_code == 400

    def test_duree_mois_envoyee_est_ignoree(self):
        """Même si le client en envoie une, le barème fait foi."""
        member = MemberFactory()

        res = _api(_comite_superuser()).post(
            URL, _payload(member, montant="100000", duree_mois=99), format="json",
        )

        assert res.status_code == 201
        assert Loan.objects.get(member=member).duree_mois == 3


# --- Non-régression du parcours en ligne ------------------------------------


def test_le_parcours_de_demande_en_ligne_reste_intact():
    """Une demande classique n'est PAS marquée « agence » et suit son cycle."""
    member = MemberFactory()
    req = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Demande en ligne",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        frais_demande_credit_paye=True,
    )

    from apps_coop.loans.services import approve_loan_request

    loan = approve_loan_request(req, decided_by=None, date_premiere_echeance=_ECHEANCE)

    req.refresh_from_db()
    assert loan.statut == Loan.Statut.ACTIF
    assert not (req.extra_payload or {}).get("octroye_en_agence")
    assert not AuditLog.objects.filter(
        action="loan.created_in_agency", entite_id=loan.id,
    ).exists()


# --- Le credit appartient VRAIMENT au membre --------------------------------
#
# Un credit accorde au guichet doit etre indiscernable, du point de vue du
# membre, d'un credit obtenu par le parcours en ligne : il le voit dans son
# espace, il est le seul a le voir, et l'agent qui l'a accorde reste trace.


class TestRattachementAuMembre:
    def test_le_membre_voit_le_credit_dans_son_espace(self):
        member = MemberFactory()
        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Octroi en seance", date_premiere_echeance=_ECHEANCE,
        )

        res = _api(member.user).get("/api/v1/loans/me/active/")

        assert res.status_code == 200
        dossiers = [r["numero_dossier"] for r in res.json()]
        assert loan.numero_dossier in dossiers

    def test_aucun_autre_membre_ne_le_voit(self):
        beneficiaire = MemberFactory()
        etranger = MemberFactory()
        create_agency_loan(
            member=beneficiaire, montant=Decimal("100000"),
            motif="Octroi en seance", date_premiere_echeance=_ECHEANCE,
        )

        res = _api(etranger.user).get("/api/v1/loans/me/active/")

        assert res.status_code == 200
        assert res.json() == []

    def test_le_loan_et_sa_demande_pointent_le_meme_membre(self):
        member = MemberFactory()
        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Octroi en seance", date_premiere_echeance=_ECHEANCE,
        )

        assert loan.member_id == member.id
        assert loan.loan_request.member_id == member.id
        # Les echeances suivent le meme credit.
        assert all(e.loan_id == loan.id for e in loan.installments.all())

    def test_lagent_qui_a_accorde_reste_trace(self):
        """Qui a decide doit rester identifiable apres coup."""
        member = MemberFactory()
        agent = _comite_superuser()

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Octroi en seance", date_premiere_echeance=_ECHEANCE,
            actor=agent,
        )

        assert loan.loan_request.decide_par_id == agent.id
        log = AuditLog.objects.filter(
            action="loan.created_in_agency", entite_id=loan.id,
        ).latest("id")
        assert log.user_id == agent.id

    def test_le_membre_est_notifie_comme_pour_un_credit_en_ligne(self):
        """`loan.approved` est emis : le membre apprend son octroi."""
        from apps_coop.notifications.models import EmailTemplate

        EmailTemplate.objects.update_or_create(
            code="loan.approved",
            defaults={
                "objet": "Credit accorde",
                "corps_html": "<p>{{ numero_dossier }}</p>",
                "corps_texte": "{{ numero_dossier }}",
                "actif": True,
            },
        )
        member = MemberFactory()
        member.user.email = "membre@test.local"
        member.user.save(update_fields=["email"])

        loan = create_agency_loan(
            member=member, montant=Decimal("100000"),
            motif="Octroi en seance", date_premiere_echeance=_ECHEANCE,
        )

        from apps_coop.notifications.models import EmailLog

        assert EmailLog.objects.filter(
            template_id="loan.approved", member=member,
        ).exists(), f"aucune notification pour {loan.numero_dossier}"
