"""Historique des débits manuels — ``GET /payments/admin/manual-debits/``.

Le débit manuel n'a pas de table à lui : selon le cas il écrit dans le registre
collecte, dans l'épargne classique, dans une collecte particulière, ou crée un
Payment pour un frais prélevé. Les trois gestes n'avaient donc aucune vue
commune — l'admin ne pouvait pas répondre à « qu'a-t-on sorti de ce compte le
mois dernier ? ».

L'historique est reconstruit depuis le journal d'audit, seul endroit qui les
réunit. Conséquence heureuse : il couvre aussi les débits antérieurs à cet
écran, sans reprise de données.

Ces tests figent la lecture, les filtres, et le fait que l'écran reste en
lecture seule.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.audit.models import AuditLog
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/payments/admin/manual-debits/"
DEBIT = "/api/v1/payments/admin/manual-debit/"


def _api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def _crediter_classique(member, montant="50000"):
    """Alimente l'épargne classique pour pouvoir débiter ensuite."""
    from apps_coop.savings.models import ClassicSavingsAccount

    account, cree = ClassicSavingsAccount.objects.get_or_create(
        member=member,
        defaults={"solde": Decimal(montant), "date_ouverture": date(2026, 1, 1)},
    )
    if not cree:
        account.solde = Decimal(montant)
        account.save(update_fields=["solde"])
    return account


# --- Lecture ----------------------------------------------------------------


class TestLecture:
    def test_un_retrait_apparait_dans_l_historique(self, active_member, admin_user):
        _crediter_classique(active_member)
        api = _api(admin_user)

        r = api.post(
            DEBIT,
            {
                "member_id": active_member.id,
                "compte": "classique",
                "montant": "7000",
                "motif": "Retrait guichet",
            },
            format="json",
        )
        assert r.status_code == 200, r.content

        body = api.get(URL).json()

        assert body["count"] == 1
        ligne = body["results"][0]
        assert ligne["nature"] == "retrait"
        assert ligne["compte"] == "classique"
        assert ligne["compte_label"] == "Épargne classique"
        assert Decimal(ligne["montant"]) == Decimal("7000")
        assert ligne["motif"] == "Retrait guichet"

    def test_la_ligne_porte_le_membre_et_l_acteur(self, active_member, admin_user):
        _crediter_classique(active_member)
        api = _api(admin_user)
        api.post(
            DEBIT,
            {"member_id": active_member.id, "compte": "classique", "montant": "1000"},
            format="json",
        )

        ligne = api.get(URL).json()["results"][0]

        assert ligne["member"]["id"] == active_member.id
        assert ligne["member"]["numero_membre"] == active_member.numero_membre
        assert ligne["acteur"] is not None
        assert ligne["acteur"]["id"] == admin_user.id

    def test_le_solde_apres_est_rapporte(self, active_member, admin_user):
        """C'est ce qui permet de relire une séance de guichet sans ouvrir le
        registre ligne à ligne."""
        _crediter_classique(active_member, "50000")
        api = _api(admin_user)
        api.post(
            DEBIT,
            {"member_id": active_member.id, "compte": "classique", "montant": "20000"},
            format="json",
        )

        ligne = api.get(URL).json()["results"][0]

        assert Decimal(ligne["solde_apres"]) == Decimal("30000")

    def test_du_plus_recent_au_plus_ancien(self, active_member, admin_user):
        _crediter_classique(active_member, "50000")
        api = _api(admin_user)
        for montant in ("1000", "2000", "3000"):
            api.post(
                DEBIT,
                {
                    "member_id": active_member.id,
                    "compte": "classique",
                    "montant": montant,
                },
                format="json",
            )

        montants = [Decimal(r["montant"]) for r in api.get(URL).json()["results"]]

        assert montants == [Decimal("3000"), Decimal("2000"), Decimal("1000")]

    def test_couvre_les_debits_anterieurs_a_l_ecran(self, active_member, admin_user):
        """L'historique se lit depuis l'audit : un débit tracé avant l'existence
        de cet écran doit donc apparaître sans aucune reprise de données."""
        AuditLog.objects.create(
            action="savings.manual_debit",
            entite_type="ClassicSavingsTransaction",
            entite_id=4242,
            user=admin_user,
            details_json={
                "member_id": active_member.id,
                "compte": "classique",
                "montant": "9000",
                "motif": "Ancien retrait",
                "solde_apres": "1000",
            },
        )

        body = _api(admin_user).get(URL).json()

        assert body["count"] == 1
        assert body["results"][0]["motif"] == "Ancien retrait"


# --- Frais prélevés ---------------------------------------------------------


def test_un_frais_preleve_apparait_comme_tel(active_member, admin_user):
    from apps_coop.payments.models import FeeType

    _crediter_classique(active_member)
    FeeType.objects.update_or_create(
        code=FeeType.Code.CARNET, defaults={"montant": Decimal("2000"), "actif": True},
    )
    api = _api(admin_user)

    r = api.post(
        DEBIT,
        {"member_id": active_member.id, "fee_code": FeeType.Code.CARNET},
        format="json",
    )
    assert r.status_code == 200, r.content

    ligne = api.get(URL).json()["results"][0]

    assert ligne["nature"] == "frais"
    assert ligne["fee_code"] == FeeType.Code.CARNET


# --- Filtres ----------------------------------------------------------------


class TestFiltres:
    def test_filtre_par_membre(self, active_member, admin_user):
        autre = MemberFactory()
        _crediter_classique(active_member)
        _crediter_classique(autre)
        api = _api(admin_user)
        for m in (active_member, autre):
            api.post(
                DEBIT,
                {"member_id": m.id, "compte": "classique", "montant": "1000"},
                format="json",
            )

        body = api.get(URL, {"member": active_member.id}).json()

        assert body["count"] == 1
        assert body["results"][0]["member"]["id"] == active_member.id

    def test_filtre_par_compte(self, active_member, admin_user):
        _crediter_classique(active_member)
        api = _api(admin_user)
        api.post(
            DEBIT,
            {"member_id": active_member.id, "compte": "classique", "montant": "1000"},
            format="json",
        )

        assert api.get(URL, {"compte": "classique"}).json()["count"] == 1
        assert api.get(URL, {"compte": "collecte"}).json()["count"] == 0

    def test_pagination(self, active_member, admin_user):
        _crediter_classique(active_member, "90000")
        api = _api(admin_user)
        for _ in range(3):
            api.post(
                DEBIT,
                {"member_id": active_member.id, "compte": "classique", "montant": "1000"},
                format="json",
            )

        body = api.get(URL, {"limit": 2}).json()

        assert body["count"] == 3
        assert len(body["results"]) == 2
        assert body["limit"] == 2


# --- Accès et innocuité -----------------------------------------------------


class TestAcces:
    def test_un_membre_simple_est_refuse(self, active_member):
        assert _api(active_member.user).get(URL).status_code in (401, 403)

    def test_anonyme_est_refuse(self):
        assert APIClient().get(URL).status_code in (401, 403)

    def test_l_ecran_ne_modifie_rien(self, active_member, admin_user):
        """Lecture seule : aucun verbe d'écriture n'est exposé."""
        api = _api(admin_user)

        assert api.post(URL, {}, format="json").status_code == 405
        assert api.delete(URL).status_code == 405

    def test_consulter_n_ecrit_pas_dans_le_journal(self, active_member, admin_user):
        avant = AuditLog.objects.count()

        _api(admin_user).get(URL)

        assert AuditLog.objects.count() == avant
