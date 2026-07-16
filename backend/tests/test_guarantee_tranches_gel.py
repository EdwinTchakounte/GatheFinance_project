"""Réforme garantie 2026 — le gel sort les tranches du pool prêteur.

Avant : le gel n'était qu'un *montant* posé sur la LoanRequest / l'
AvalisteConsent. Une épargne gelée en garantie restait sélectionnable dans
« Composer le funding » — le même argent pouvait garantir un crédit ET en
financer un autre.

Ces tests verrouillent les trois règles décidées :
  1. Le gel puise d'abord dans le PLACEMENT (tranches DISPONIBLE), puis
     déborde sur la part LIBRE (non matérialisée).
  2. Une tranche gelée sort du pool (capacite_pretable, funding) mais reste
     du placement actif (le retirable ne bouge pas d'un XAF).
  3. Le gel est rendu au pool au rejet de la demande et à la clôture du crédit.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.loans.guarantee_tranches import (
    earmark_guarantee_tranches,
    release_guarantee_tranches,
)
from apps_coop.loans.models import Loan, LoanRequest
from apps_coop.savings.models import ClassicSavingsAccount, LenderTranche
from apps_coop.savings.services import classic_withdrawable
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.audit.models import AppSetting
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


def _member_with_savings(solde, *, placements=()):
    """Membre avec un solde classique total et, dedans, des tranches de placement.

    ``solde`` est le TOTAL (le placement en est un sous-ensemble : cf.
    ``solde_libre = solde − solde_placement_actif``).
    """
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount", defaults={"valeur": "1000"}
    )
    m = MemberFactory()
    ClassicSavingsAccount.objects.create(
        member=m, solde=Decimal(solde), date_ouverture=date.today()
    )
    if placements:
        opt_in_lender(member=m, is_global=False)
        for p in placements:
            add_tranche(member=m, montant=Decimal(p))
    return m


def _lr(member, montant=Decimal("50000")):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal(montant),
        duree_mois=3,
        motif="Test gel garantie",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )


def _gelees(member):
    return LenderTranche.objects.filter(
        member=member, statut=LenderTranche.Statut.GELEE
    )


def _dispo_total(member):
    from django.db.models import Sum

    return LenderTranche.objects.filter(
        member=member, statut=LenderTranche.Statut.DISPONIBLE
    ).aggregate(s=Sum("montant"))["s"] or Decimal("0")


# ---------------------------------------------------------------------------
# 1 — Ordre de service : placement d'abord, libre ensuite
# ---------------------------------------------------------------------------


class TestOrdreDeService:
    def test_gel_puise_dans_le_placement_en_premier(self):
        # 100k de solde dont 60k placés en 2 tranches. On gèle 50k → tout doit
        # sortir du placement, la part libre n'est pas touchée.
        m = _member_with_savings("100000", placements=["30000", "30000"])
        lr = _lr(m)

        gele = earmark_guarantee_tranches(
            member=m, montant=Decimal("50000"), loan_request=lr
        )

        assert gele == Decimal("50000"), "le placement couvrait tout le gel"
        assert sum(Decimal(t.montant) for t in _gelees(m)) == Decimal("50000")
        # Il reste 10k de placement prêtable (60k − 50k).
        assert _dispo_total(m) == Decimal("10000")

    def test_gel_deborde_sur_le_libre_quand_le_placement_ne_suffit_pas(self):
        # 100k de solde dont 20k placés. On gèle 50k → 20k sur le placement,
        # les 30k restants mordent sur le libre (non matérialisé en tranche).
        m = _member_with_savings("100000", placements=["20000"])
        lr = _lr(m)

        gele = earmark_guarantee_tranches(
            member=m, montant=Decimal("50000"), loan_request=lr
        )

        assert gele == Decimal("20000"), "seul le placement est matérialisable"
        assert _dispo_total(m) == Decimal("0"), "tout le placement est gelé"

    def test_la_derniere_tranche_est_splittee_au_besoin(self):
        # On gèle 25k sur une seule tranche de 30k → 25k GELEE + 5k DISPONIBLE.
        m = _member_with_savings("100000", placements=["30000"])
        lr = _lr(m)

        earmark_guarantee_tranches(
            member=m, montant=Decimal("25000"), loan_request=lr
        )

        assert sum(Decimal(t.montant) for t in _gelees(m)) == Decimal("25000")
        assert _dispo_total(m) == Decimal("5000"), "le surplus retourne au pool"
        # Le split ne crée pas d'argent : le placement actif est inchangé.
        acct = ClassicSavingsAccount.objects.get(member=m)
        assert acct.solde_placement_actif == Decimal("30000")

    def test_gel_sans_placement_ne_cree_aucune_tranche(self):
        m = _member_with_savings("100000")
        lr = _lr(m)

        gele = earmark_guarantee_tranches(
            member=m, montant=Decimal("50000"), loan_request=lr
        )

        assert gele == Decimal("0")
        assert not _gelees(m).exists()


# ---------------------------------------------------------------------------
# 2 — Une tranche gelée sort du pool, mais reste du placement
# ---------------------------------------------------------------------------


class TestSortieDuPool:
    def test_tranche_gelee_nest_plus_pretable_mode_b(self):
        m = _member_with_savings("100000", placements=["60000"])
        assert m.capacite_pretable == Decimal("60000")

        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=_lr(m)
        )

        m.refresh_from_db()
        assert m.capacite_pretable == Decimal("0"), (
            "l'épargne gelée en garantie ne doit plus pouvoir financer un crédit"
        )

    def test_tranche_gelee_nest_plus_pretable_mode_a(self):
        """Mode A (global) : le pool est le solde brut, pas les tranches — il
        faut soustraire le gel explicitement, sinon la sortie du pool est
        contournée par la branche globale."""
        m = _member_with_savings("100000")
        opt_in_lender(member=m, is_global=True)
        assert m.capacite_pretable == Decimal("100000")

        lr = _lr(m, montant=Decimal("40000"))
        lr.montant_gele_demandeur = Decimal("40000")
        lr.save(update_fields=["montant_gele_demandeur"])

        m.refresh_from_db()
        assert m.capacite_pretable == Decimal("60000")

    def test_le_gel_ne_change_pas_le_retirable(self):
        """Garde-fou anti-régression : marquer les tranches GELEE ne doit pas
        déplacer d'un XAF ce que le membre peut retirer. Si GELEE sortait de
        ``solde_placement_actif``, le retirable augmenterait — l'argent gelé
        deviendrait retirable."""
        m = _member_with_savings("100000", placements=["60000"])
        acct = ClassicSavingsAccount.objects.get(member=m)
        avant = classic_withdrawable(acct)
        assert avant == Decimal("40000")  # 100k − placement 60k

        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=_lr(m)
        )

        acct.refresh_from_db()
        assert acct.solde_placement_actif == Decimal("60000")
        assert classic_withdrawable(acct) == avant


# ---------------------------------------------------------------------------
# 3 — Libération
# ---------------------------------------------------------------------------


class TestLiberation:
    def test_release_rend_les_tranches_au_pool(self):
        m = _member_with_savings("100000", placements=["60000"])
        lr = _lr(m)
        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=lr
        )
        assert _dispo_total(m) == Decimal("0")

        n = release_guarantee_tranches(lr)

        assert n == 1
        assert _dispo_total(m) == Decimal("60000")
        assert not _gelees(m).exists()

    def test_release_est_idempotent(self):
        m = _member_with_savings("100000", placements=["60000"])
        lr = _lr(m)
        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=lr
        )
        release_guarantee_tranches(lr)
        assert release_guarantee_tranches(lr) == 0

    def test_rejet_de_la_demande_libere_automatiquement(self):
        """Le gel n'a aucun point de libération explicite dans le métier (il est
        dérivé des statuts). Le signal doit donc rendre la main tout seul."""
        m = _member_with_savings("100000", placements=["60000"])
        lr = _lr(m)
        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=lr
        )

        lr.statut = LoanRequest.Statut.REJETEE
        lr.motif_rejet = "Test"
        lr.save()

        assert _dispo_total(m) == Decimal("60000")

    def test_cloture_du_credit_libere_automatiquement(self):
        m = _member_with_savings("100000", placements=["60000"])
        lr = _lr(m)
        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=lr
        )
        loan = Loan.objects.create(
            member=m,
            loan_request=lr,
            numero_dossier="GF-CR-GEL-1",
            montant=Decimal("50000"),
            taux_interet=Decimal("0.10"),
            duree_mois=3,
            date_decaissement=date.today(),
            date_premiere_echeance=date.today() + timedelta(days=30),
            montant_total_du=Decimal("55000"),
            solde_restant=Decimal("55000"),
            statut=Loan.Statut.ACTIF,
        )
        assert _dispo_total(m) == Decimal("0"), "gel vivant tant que le crédit court"

        loan.statut = Loan.Statut.CLOTURE
        loan.solde_restant = Decimal("0")
        loan.save()

        assert _dispo_total(m) == Decimal("60000")

    def test_une_tranche_engagee_nest_pas_recuperee_par_le_release(self):
        """Si une tranche a été engagée dans un funding entre-temps, la chute du
        gel ne doit pas la ramener au pool : l'argent finance un crédit vivant,
        seul le funding décide de le libérer."""
        m = _member_with_savings("100000", placements=["60000"])
        lr = _lr(m)
        earmark_guarantee_tranches(
            member=m, montant=Decimal("60000"), loan_request=lr
        )
        t = _gelees(m).get()
        t.statut = LenderTranche.Statut.ENGAGEE
        t.save(update_fields=["statut"])

        assert release_guarantee_tranches(lr) == 0
        t.refresh_from_db()
        assert t.statut == LenderTranche.Statut.ENGAGEE
