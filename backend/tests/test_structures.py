"""Structures employeur & paie des employés — cagnotte approvisionnée, paie
(lot + individuel) créditée dans l'épargne classique LIBRE, retirable ensuite."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.savings.models import ClassicSavingsAccount
from apps_coop.structures import services as svc
from apps_coop.structures.models import (
    PayrollRun,
    Structure,
    StructureEmployee,
    StructureTransaction,
)
from tests.factories import MemberFactory

pytestmark = pytest.mark.django_db

_JAN = datetime.date(2026, 1, 1)


def _structure_with_two_employees():
    s = svc.create_structure(nom="ACME SARL")
    a = MemberFactory()
    b = MemberFactory()
    e1 = svc.add_employee(s, a, poste="Vendeur", montant_paie=Decimal("60000"))
    e2 = svc.add_employee(s, b, poste="Caissier", montant_paie=Decimal("40000"))
    return s, (a, e1), (b, e2)


class TestEmployees:
    def test_add_update_remove_employee(self):
        s, (a, e1), (b, e2) = _structure_with_two_employees()
        assert s.employees.filter(actif=True).count() == 2
        # Modifier le montant + poste.
        svc.update_employee(e1, poste="Chef de rayon", montant_paie=Decimal("75000"))
        e1.refresh_from_db()
        assert e1.montant_paie == Decimal("75000") and e1.poste == "Chef de rayon"
        # Retirer (soft) → reste en base mais inactif.
        svc.remove_employee(e2)
        e2.refresh_from_db()
        assert e2.actif is False
        assert s.employees.filter(actif=True).count() == 1

    def test_employee_unique_per_structure(self):
        s = svc.create_structure(nom="X")
        m = MemberFactory()
        svc.add_employee(s, m, montant_paie=Decimal("1000"))
        # Ré-ajout = réactivation/maj, pas de doublon.
        svc.add_employee(s, m, montant_paie=Decimal("2000"))
        assert StructureEmployee.objects.filter(structure=s, member=m).count() == 1
        assert StructureEmployee.objects.get(structure=s, member=m).montant_paie == Decimal("2000")


class TestCagnotte:
    def test_fund_and_withdraw(self):
        s = svc.create_structure(nom="X")
        svc.fund_structure(structure=s, montant=Decimal("100000"))
        s.refresh_from_db()
        assert s.solde == Decimal("100000")
        svc.withdraw_funds(structure=s, montant=Decimal("30000"))
        s.refresh_from_db()
        assert s.solde == Decimal("70000")

    def test_withdraw_capped(self):
        s = svc.create_structure(nom="X")
        svc.fund_structure(structure=s, montant=Decimal("10000"))
        with pytest.raises(svc.StructureError, match="insuffisante"):
            svc.withdraw_funds(structure=s, montant=Decimal("20000"))


class TestPayroll:
    def test_run_payroll_credits_free_savings(self):
        s, (a, e1), (b, e2) = _structure_with_two_employees()  # 60000 + 40000
        svc.fund_structure(structure=s, montant=Decimal("100000"))
        run = svc.run_payroll(structure=s, periode="Août 2026")
        s.refresh_from_db()
        assert s.solde == Decimal("0")  # 100000 - 100000
        assert run.total_verse == Decimal("100000") and run.employes_count == 2
        # Chaque employé a sa paie dans l'épargne classique LIBRE (retirable).
        acc_a = ClassicSavingsAccount.objects.get(member=a)
        acc_b = ClassicSavingsAccount.objects.get(member=b)
        assert acc_a.solde == Decimal("60000") and acc_a.solde_libre == Decimal("60000")
        assert acc_b.solde == Decimal("40000")

    def test_run_payroll_insufficient_pays_nobody(self):
        """Atomique : si la cagnotte ne couvre pas le total, personne n'est payé."""
        s, (a, e1), (b, e2) = _structure_with_two_employees()  # total 100000
        svc.fund_structure(structure=s, montant=Decimal("50000"))
        with pytest.raises(svc.StructureError, match="insuffisante"):
            svc.run_payroll(structure=s, periode="Août 2026")
        s.refresh_from_db()
        assert s.solde == Decimal("50000")  # inchangé
        assert not ClassicSavingsAccount.objects.filter(member=a).exists()
        assert PayrollRun.objects.count() == 0

    def test_pay_single_employee(self):
        s, (a, e1), (b, e2) = _structure_with_two_employees()
        svc.fund_structure(structure=s, montant=Decimal("100000"))
        # Paie individuelle avec un montant custom (prime).
        svc.pay_employee(structure=s, employee=e1, montant=Decimal("15000"))
        s.refresh_from_db()
        assert s.solde == Decimal("85000")
        assert ClassicSavingsAccount.objects.get(member=a).solde == Decimal("15000")

    def test_paid_salary_is_withdrawable(self):
        """La paie versée est bien retirable par l'employé (épargne libre)."""
        from apps_coop.savings.models import WithdrawalRequest
        from apps_coop.savings.services import request_withdrawal

        s, (a, e1), (b, e2) = _structure_with_two_employees()
        svc.fund_structure(structure=s, montant=Decimal("100000"))
        svc.pay_employee(structure=s, employee=e1)  # 60000 → épargne libre de a
        acc = ClassicSavingsAccount.objects.get(member=a)
        assert acc.solde_libre == Decimal("60000")
        # a peut initier un retrait de 20000 sur sa part libre.
        wr = request_withdrawal(
            classic_account=acc,
            montant=Decimal("20000"),
            source=WithdrawalRequest.Source.CLASSIQUE_LIBRE,
            mode_paiement=WithdrawalRequest.ModePaiement.PRESENTIEL,
        )
        assert wr is not None and wr.montant == Decimal("20000")


class TestApi:
    def _admin(self, admin_user):
        c = APIClient()
        c.force_authenticate(user=admin_user)
        return c

    def test_full_flow_via_api(self, admin_user):
        c = self._admin(admin_user)
        # Créer
        r = c.post("/api/v1/structures/admin/structures/", {"nom": "API SARL"}, format="json")
        assert r.status_code == 201, r.content
        sid = r.json()["id"]
        # Ajouter un employé
        m = MemberFactory()
        r = c.post(f"/api/v1/structures/admin/structures/{sid}/employees/add/",
                   {"member_id": m.id, "poste": "Dev", "montant_paie": 50000}, format="json")
        assert r.status_code == 200, r.content
        assert r.json()["employees_count"] == 1
        emp_id = r.json()["employees"][0]["id"]
        # Approvisionner
        c.post(f"/api/v1/structures/admin/structures/{sid}/fund/", {"montant": 80000}, format="json")
        # Modifier le montant
        c.post(f"/api/v1/structures/admin/structures/{sid}/employees/{emp_id}/update/",
               {"montant_paie": 55000}, format="json")
        # Verser le lot
        r = c.post(f"/api/v1/structures/admin/structures/{sid}/run-payroll/",
                   {"periode": "Août 2026"}, format="json")
        assert r.status_code == 200, r.content
        assert Decimal(r.json()["solde"]) == Decimal("25000")  # 80000 - 55000
        assert ClassicSavingsAccount.objects.get(member=m).solde == Decimal("55000")

    def test_requires_staff(self, active_member):
        c = APIClient()
        c.force_authenticate(user=active_member.user)  # membre, non-staff
        r = c.post("/api/v1/structures/admin/structures/", {"nom": "X"}, format="json")
        assert r.status_code in (401, 403)

    def test_payroll_pdf(self, admin_user):
        s = svc.create_structure(nom="PDF SARL", by=admin_user)
        m = MemberFactory()
        e = svc.add_employee(s, m, poste="Dev", montant_paie=Decimal("50000"))
        svc.fund_structure(structure=s, montant=Decimal("50000"), by=admin_user)
        run = svc.run_payroll(structure=s, periode="Août 2026", by=admin_user)
        r = self._admin(admin_user).get(
            f"/api/v1/structures/admin/structures/{s.id}/payroll/{run.id}/pdf/"
        )
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content[:4] == b"%PDF"


class TestNotifications:
    def test_salary_notifies_employee(self, admin_user):
        from apps_coop.notifications.models import Notification

        s = svc.create_structure(nom="Notif SARL", by=admin_user)
        m = MemberFactory()
        e = svc.add_employee(s, m, montant_paie=Decimal("30000"))
        svc.fund_structure(structure=s, montant=Decimal("30000"), by=admin_user)
        svc.run_payroll(structure=s, periode="Août 2026", by=admin_user)
        notifs = Notification.objects.filter(user=m.user, type="structure.paie")
        assert notifs.exists()
        assert "30000" in notifs.latest("id").message
