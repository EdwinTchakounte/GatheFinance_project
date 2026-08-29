"""Écritures antidatées — reprise d'historique des carnets papier.

Décision métier gelée : reprise d'historique SEULE. Une écriture antidatée est
enregistrée à sa vraie date et ne déclenche AUCUN traitement (pas de clôture
rejouée, pas de Payment, pas de notification). Le seul effet est comptable :
la ligne de grand livre est créée et le solde ajusté.

Invariant visé : somme des écritures = solde du carnet papier.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps_coop.members.models import BookletOrder
from apps_coop.payments.models import Payment
from apps_coop.savings.antidated_services import (
    AntidatedEntryError,
    create_antidated_booklet,
    record_antidated_entry,
)
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    ClassicSavingsTransaction,
    SavingsAccount,
    SavingsTransaction,
)
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


MARS = date(2026, 3, 15)
AVRIL = date(2026, 4, 20)


def _booklet(member, created_on):
    """Carnet réel (avec son Payment) daté du jour ``created_on``."""
    from django.utils import timezone

    p = Payment.objects.create(
        member=member,
        montant=Decimal("1000"),
        type=Payment.Type.FRAIS_CARNET,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )
    order = BookletOrder.objects.create(member=member, payment=p)
    BookletOrder.objects.filter(id=order.id).update(created_at=_dt(created_on))
    order.refresh_from_db()
    return order


def _staff():
    m = MemberFactory()
    m.user.is_staff = True
    m.user.is_superuser = True
    m.user.save(update_fields=["is_staff", "is_superuser"])
    return m


# ---------------------------------------------------------------------------
# Service — collectes particulières (tontine / caisse scolaire)
# ---------------------------------------------------------------------------


class TestSpecialCollections:
    def _setup(self, product_type="tontine_alimentaire"):
        from apps_coop.special_collections.models import (
            SpecialCollectionMembership,
        )
        from apps_coop.special_collections.services import open_cycle

        m = MemberFactory()
        cycle = open_cycle(type=product_type, nom="Reprise")
        membership = SpecialCollectionMembership.objects.create(
            member=m, cycle=cycle, type=product_type,
            statut=SpecialCollectionMembership.Statut.VALIDE, objectif="x",
        )
        return m, cycle, membership

    def test_depot_antidate_tontine_credite(self):
        from apps_coop.special_collections.models import (
            SpecialCollectionTransaction,
        )

        m, cycle, membership = self._setup("tontine_alimentaire")
        res = record_antidated_entry(
            member=m, product="tontine", sens="depot",
            montant=Decimal("7000"), date_op=MARS, cycle_id=cycle.id,
        )
        assert res.solde_apres == Decimal("7000")
        membership.refresh_from_db()
        assert membership.solde == Decimal("7000")
        row = SpecialCollectionTransaction.objects.get(pk=res.transaction_id)
        assert row.type_op == SpecialCollectionTransaction.TypeOp.MANUEL
        assert row.date is not None  # date effective posée

    def test_cycle_id_obligatoire(self):
        m, _cycle, _membership = self._setup("caisse_scolaire")
        with pytest.raises(AntidatedEntryError, match="cycle_id|collecte"):
            record_antidated_entry(
                member=m, product="caisse_scolaire", sens="depot",
                montant=Decimal("1000"), date_op=MARS,
            )

    def test_retrait_antidate_special_peut_etre_negatif(self):
        m, cycle, membership = self._setup("tontine_alimentaire")
        res = record_antidated_entry(
            member=m, product="tontine", sens="retrait",
            montant=Decimal("3000"), date_op=MARS, cycle_id=cycle.id,
        )
        assert res.solde_apres == Decimal("-3000")


# ---------------------------------------------------------------------------
# Service — collecte
# ---------------------------------------------------------------------------


class TestCollecte:
    def test_depot_antidate_credite_et_date(self):
        m = MemberFactory()
        res = record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=MARS,
        )
        assert res.solde_apres == Decimal("10000")
        assert SavingsAccount.objects.get(member=m).solde == Decimal("10000")

        row = SavingsTransaction.objects.get(id=res.transaction_id)
        assert row.type_op == SavingsTransaction.TypeOp.DEPOT
        assert row.date.date() == MARS
        assert row.payment is None, "aucun Payment : pas d'encaissement réel"

    def test_retrait_antidate_debite(self):
        m = MemberFactory()
        record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=MARS,
        )
        res = record_antidated_entry(
            member=m, product="collecte", sens="retrait",
            montant=Decimal("4000"), date_op=AVRIL,
        )
        assert res.solde_apres == Decimal("6000")
        assert SavingsAccount.objects.get(member=m).solde == Decimal("6000")

    def test_cree_le_compte_collecte_si_absent(self):
        """Reprise d'historique d'un membre SANS compte collecte : le
        get_or_create doit fournir date_ouverture (NOT NULL) — sinon
        IntegrityError. La fabrique de test pré-crée le compte, ce qui masquait
        ce chemin ; on le force en supprimant le compte d'abord.
        """
        m = MemberFactory()
        SavingsAccount.objects.filter(member=m).delete()
        assert not SavingsAccount.objects.filter(member=m).exists()

        record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=date(2026, 1, 20),
        )

        acct = SavingsAccount.objects.get(member=m)
        assert acct.solde == Decimal("10000")
        assert acct.date_ouverture == date(2026, 1, 20)

    def test_somme_des_ecritures_egale_le_solde(self):
        """L'invariant central de la reprise d'historique."""
        m = MemberFactory()
        mouvements = [
            ("depot", "5000", date(2026, 1, 10)),
            ("depot", "3000", date(2026, 2, 5)),
            ("retrait", "2000", date(2026, 2, 20)),
            ("depot", "7000", date(2026, 3, 1)),
        ]
        for sens, montant, d in mouvements:
            record_antidated_entry(
                member=m, product="collecte", sens=sens,
                montant=Decimal(montant), date_op=d,
            )
        # 5000 + 3000 − 2000 + 7000 = 13000
        assert SavingsAccount.objects.get(member=m).solde == Decimal("13000")
        assert SavingsTransaction.objects.filter(account__member=m).count() == 4

    def test_retrait_antidate_peut_rendre_solde_negatif(self):
        """Reprise d'historique : un retrait antidaté supérieur au solde du
        moment est accepté et le solde passe négatif (retrait 5000 sur 1000)."""
        m = MemberFactory()
        record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("1000"), date_op=MARS,
        )
        res = record_antidated_entry(
            member=m, product="collecte", sens="retrait",
            montant=Decimal("5000"), date_op=AVRIL,
        )
        assert res.solde_apres == Decimal("-4000")
        assert SavingsAccount.objects.get(member=m).solde == Decimal("-4000")
        assert SavingsTransaction.objects.filter(account__member=m).count() == 2


# ---------------------------------------------------------------------------
# Service — épargne classique
# ---------------------------------------------------------------------------


class TestClassique:
    def test_depot_antidate_credite(self):
        m = MemberFactory()
        res = record_antidated_entry(
            member=m, product="classique", sens="depot",
            montant=Decimal("50000"), date_op=MARS,
        )
        assert res.solde_apres == Decimal("50000")
        acct = ClassicSavingsAccount.objects.get(member=m)
        assert acct.solde == Decimal("50000")
        # Pas de placement matérialisé : reste librement retirable.
        assert acct.solde_libre == Decimal("50000")

        row = ClassicSavingsTransaction.objects.get(id=res.transaction_id)
        assert row.type_op == ClassicSavingsTransaction.TypeOp.DEPOT
        assert row.date.date() == MARS
        assert row.payment is None

    def test_ouvre_le_compte_a_la_date_de_lecriture(self):
        m = MemberFactory()
        assert not ClassicSavingsAccount.objects.filter(member=m).exists()
        record_antidated_entry(
            member=m, product="classique", sens="depot",
            montant=Decimal("50000"), date_op=MARS,
        )
        acct = ClassicSavingsAccount.objects.get(member=m)
        assert acct.date_ouverture == MARS


# ---------------------------------------------------------------------------
# Rattachement au carnet actif à la date
# ---------------------------------------------------------------------------


class TestRattachementCarnet:
    def test_ecriture_pointe_le_carnet_actif_a_sa_date(self):
        """Le piège : latest_for rattache au carnet le plus récent. Une écriture
        de mars doit pointer le carnet de mars, pas celui commandé en avril."""
        m = MemberFactory()
        carnet_mars = _booklet(m, date(2026, 3, 1))
        _booklet(m, date(2026, 4, 1))

        res = record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=date(2026, 3, 15),
        )
        row = SavingsTransaction.objects.get(id=res.transaction_id)
        assert row.booklet_order_id == carnet_mars.id

    def test_date_anterieure_a_tout_carnet_retombe_sur_le_plus_ancien(self):
        m = MemberFactory()
        carnet = _booklet(m, date(2026, 6, 1))

        res = record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=date(2026, 1, 15),
        )
        row = SavingsTransaction.objects.get(id=res.transaction_id)
        assert row.booklet_order_id == carnet.id

    def test_carnet_explicite_dun_autre_membre_refuse(self):
        m = MemberFactory()
        autre = MemberFactory()
        carnet_autre = _booklet(autre, date(2026, 3, 1))
        with pytest.raises(AntidatedEntryError, match="n'appartient pas"):
            record_antidated_entry(
                member=m, product="collecte", sens="depot",
                montant=Decimal("10000"), date_op=MARS,
                booklet_order=carnet_autre,
            )


# ---------------------------------------------------------------------------
# Validations
# ---------------------------------------------------------------------------


class TestValidations:
    def test_date_future_refusee(self):
        m = MemberFactory()
        futur = date.today() + timedelta(days=5)
        with pytest.raises(AntidatedEntryError, match="futur"):
            record_antidated_entry(
                member=m, product="collecte", sens="depot",
                montant=Decimal("1000"), date_op=futur,
            )

    def test_montant_negatif_refuse(self):
        m = MemberFactory()
        with pytest.raises(AntidatedEntryError):
            record_antidated_entry(
                member=m, product="collecte", sens="depot",
                montant=Decimal("-1"), date_op=MARS,
            )

    def test_produit_inconnu_refuse(self):
        m = MemberFactory()
        with pytest.raises(AntidatedEntryError, match="Produit"):
            record_antidated_entry(
                member=m, product="livret_a", sens="depot",
                montant=Decimal("1000"), date_op=MARS,
            )


# ---------------------------------------------------------------------------
# Carnet antidaté
# ---------------------------------------------------------------------------


class TestCarnetAntidate:
    def test_cree_un_carnet_date_dans_le_passe(self):
        m = MemberFactory()
        res = create_antidated_booklet(member=m, date_op=MARS)

        booklet = BookletOrder.objects.get(id=res.booklet_order_id)
        assert booklet.created_at.date() == MARS
        assert booklet.statut == BookletOrder.Statut.DELIVREE
        assert booklet.annee == 2026
        # Un Payment technique existe (schéma OneToOne obligatoire), à 0 par
        # défaut pour ne pas gonfler les recettes.
        assert booklet.payment.montant == Decimal("0")
        assert booklet.payment.type == Payment.Type.FRAIS_CARNET

    def test_ne_cree_pas_de_second_carnet_via_le_hook(self):
        """Le hook _hook_carnet_fees créerait un 2e carnet à partir du Payment
        frais_carnet. On le contourne : exactement 1 carnet."""
        # Membre sans carnet d'activation pour isoler le carnet antidaté (la
        # ``MemberFactory`` en donne un par défaut).
        m = MemberFactory(with_carnet=False)
        create_antidated_booklet(member=m, date_op=MARS)
        assert BookletOrder.objects.filter(member=m).count() == 1

    def test_les_ecritures_posterieures_sy_rattachent(self):
        """Bout en bout : carnet antidaté de mars → une écriture de mars-15 doit
        s'y rattacher automatiquement (sans booklet_order_id explicite)."""
        m = MemberFactory()
        booklet_res = create_antidated_booklet(member=m, date_op=date(2026, 3, 1))
        entry = record_antidated_entry(
            member=m, product="collecte", sens="depot",
            montant=Decimal("10000"), date_op=date(2026, 3, 15),
        )
        row = SavingsTransaction.objects.get(id=entry.transaction_id)
        assert row.booklet_order_id == booklet_res.booklet_order_id

    def test_carnet_futur_refuse(self):
        m = MemberFactory()
        with pytest.raises(AntidatedEntryError, match="futur"):
            create_antidated_booklet(
                member=m, date_op=date.today() + timedelta(days=3)
            )

    def test_endpoint_cree_le_carnet(self):
        staff = _staff()
        m = MemberFactory()
        c = APIClient()
        c.force_authenticate(user=staff.user)
        r = c.post(
            "/api/v1/savings/admin/antidated-booklet/",
            {"member_id": m.id, "date": MARS.isoformat()},
            format="json",
        )
        assert r.status_code == 201, r.content
        assert BookletOrder.objects.filter(
            id=r.json()["booklet_order_id"], member=m
        ).exists()


# ---------------------------------------------------------------------------
# Endpoint admin
# ---------------------------------------------------------------------------


class TestEndpoint:
    URL = "/api/v1/savings/admin/antidated-entry/"

    def _api(self, staff):
        c = APIClient()
        c.force_authenticate(user=staff.user)
        return c

    def test_endpoint_cree_lecriture(self):
        staff = _staff()
        m = MemberFactory()
        r = self._api(staff).post(
            self.URL,
            {
                "member_id": m.id,
                "product": "collecte",
                "sens": "depot",
                "montant": "10000",
                "date": MARS.isoformat(),
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        assert r.json()["solde_apres"] == "10000.00"
        assert SavingsAccount.objects.get(member=m).solde == Decimal("10000")

    def test_endpoint_accepte_retrait_solde_negatif(self):
        """Reprise d'historique : le retrait antidaté qui dépasse le solde est
        accepté (le solde peut passer négatif), plus de 409."""
        staff = _staff()
        m = MemberFactory()
        r = self._api(staff).post(
            self.URL,
            {
                "member_id": m.id, "product": "collecte", "sens": "retrait",
                "montant": "5000", "date": MARS.isoformat(),
            },
            format="json",
        )
        assert r.status_code == 201, r.content
        assert r.json()["solde_apres"] == "-5000.00"
        assert SavingsAccount.objects.get(member=m).solde == Decimal("-5000")

    def test_endpoint_refuse_non_staff(self):
        membre = MemberFactory()
        cible = MemberFactory()
        c = APIClient()
        c.force_authenticate(user=membre.user)
        r = c.post(
            self.URL,
            {
                "member_id": cible.id, "product": "collecte", "sens": "depot",
                "montant": "10000", "date": MARS.isoformat(),
            },
            format="json",
        )
        assert r.status_code in (401, 403)
        # MemberFactory pré-crée un SavingsAccount : on vérifie qu'aucune
        # ÉCRITURE n'a été posée, et que le solde n'a pas bougé.
        assert not SavingsTransaction.objects.filter(account__member=cible).exists()
        acct = SavingsAccount.objects.filter(member=cible).first()
        assert acct is None or acct.solde == Decimal("0")


def _dt(d):
    from datetime import datetime, time

    from django.utils import timezone

    return timezone.make_aware(
        datetime.combine(d, time(12, 0)), timezone.get_current_timezone()
    )
