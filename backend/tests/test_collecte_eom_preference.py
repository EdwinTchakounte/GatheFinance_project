"""Collecte fin de mois — choix membre (cash vs bascule épargne) + vue admin.

Le champ `end_of_month_preference` existait mais n'était jamais writable :
ces endpoints le rendent pilotable par le membre et lisible par l'admin.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.savings.models import SavingsAccount
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


def _api(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestMemberPreference:
    def test_defaut_cash(self):
        m = MemberFactory()
        r = _api(m.user).get("/api/v1/savings/me/end-of-month-preference/")
        assert r.status_code == 200
        assert r.data["preference"] == "cash"

    def test_membre_bascule_vers_epargne(self):
        m = MemberFactory()
        r = _api(m.user).post(
            "/api/v1/savings/me/end-of-month-preference/",
            {"preference": "epargne"},
        )
        assert r.status_code == 200
        assert r.data["preference"] == "epargne"
        m.savings_account.refresh_from_db()
        assert (
            m.savings_account.end_of_month_preference
            == SavingsAccount.EndOfMonthPreference.EPARGNE
        )

    def test_valeur_invalide_refusee(self):
        m = MemberFactory()
        r = _api(m.user).post(
            "/api/v1/savings/me/end-of-month-preference/",
            {"preference": "n_importe_quoi"},
        )
        assert r.status_code == 400

    def test_preference_exposee_dans_me(self):
        m = MemberFactory()
        m.savings_account.end_of_month_preference = (
            SavingsAccount.EndOfMonthPreference.EPARGNE
        )
        m.savings_account.save(update_fields=["end_of_month_preference"])
        r = _api(m.user).get("/api/v1/savings/me/")
        assert r.status_code == 200
        assert r.data["end_of_month_preference"] == "epargne"


class TestAdminPreferences:
    def test_liste_avec_summary(self):
        staff = _staff()
        a = MemberFactory()
        a.savings_account.solde = Decimal("15000")
        a.savings_account.end_of_month_preference = "epargne"
        a.savings_account.save(update_fields=["solde", "end_of_month_preference"])

        r = _api(staff.user).get("/api/v1/savings/admin/collecte-preferences/")
        assert r.status_code == 200
        assert r.data["summary"]["total"] >= 1
        row = next(
            (x for x in r.data["results"] if x["member_id"] == a.id), None
        )
        assert row is not None
        assert row["preference"] == "epargne"
        assert row["numero_membre"] == a.numero_membre

    def test_momo_destination_remontee_au_dashboard(self):
        # P9 — un membre choisit « versement MoMo sur mon compte » : la vue admin
        # doit exposer préférence mobile_money + destination (numéro/réseau),
        # sinon la coop ne peut pas exécuter le versement.
        staff = _staff()
        m = MemberFactory()
        m.savings_account.solde = Decimal("8000")
        m.savings_account.end_of_month_preference = "mobile_money"
        m.savings_account.payout_phone = "699112233"
        m.savings_account.payout_network = "MTN"
        m.savings_account.save(
            update_fields=[
                "solde", "end_of_month_preference", "payout_phone", "payout_network",
            ]
        )
        r = _api(staff.user).get("/api/v1/savings/admin/collecte-preferences/")
        assert r.status_code == 200
        assert r.data["summary"]["mobile_money"] >= 1
        row = next(x for x in r.data["results"] if x["member_id"] == m.id)
        assert row["preference"] == "mobile_money"
        assert row["payout_phone"] == "699112233"
        assert row["payout_network"] == "MTN"

    def test_only_active_filtre_solde_zero(self):
        staff = _staff()
        z = MemberFactory()  # solde 0 par défaut
        r = _api(staff.user).get(
            "/api/v1/savings/admin/collecte-preferences/?only_active=1"
        )
        assert r.status_code == 200
        ids = [x["member_id"] for x in r.data["results"]]
        assert z.id not in ids

    def test_non_staff_refuse(self):
        m = MemberFactory()
        r = _api(m.user).get("/api/v1/savings/admin/collecte-preferences/")
        assert r.status_code in (401, 403)


class TestReminderCron:
    def test_rappel_envoye_aux_actifs_avec_solde(self):
        from apps_coop.savings.tasks import collecte_eom_choice_reminder

        m = MemberFactory()
        m.savings_account.solde = Decimal("5000")
        m.savings_account.save(update_fields=["solde"])

        summary = collecte_eom_choice_reminder()
        assert summary["reminders_sent"] >= 1

    def test_rappel_ignore_solde_zero(self):
        from apps_coop.savings.tasks import collecte_eom_choice_reminder

        MemberFactory()  # solde 0 par défaut
        summary = collecte_eom_choice_reminder()
        assert summary["reminders_sent"] == 0

    def test_rappel_desactivable(self):
        from apps_coop.audit.models import AppSetting
        from apps_coop.savings.tasks import collecte_eom_choice_reminder

        m = MemberFactory()
        m.savings_account.solde = Decimal("5000")
        m.savings_account.save(update_fields=["solde"])
        AppSetting.objects.update_or_create(
            cle="collecte.eom_reminder.enabled", defaults={"valeur": "false"}
        )
        summary = collecte_eom_choice_reminder()
        assert summary.get("skipped") is True
