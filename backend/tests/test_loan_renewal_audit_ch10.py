"""CH-10 — Audit de la reconduction crédit (Art. 10/11 du Règlement).

Formalise par des tests les invariants suivants :

  - Les intérêts de reconduction portent sur **tout ce qu'il reste à
    remettre** (capital restant + intérêts résiduels), JAMAIS sur le montant
    initial du crédit. Reconduire 50 000 coûte 15 % × 50 000, en plus des
    50 000 à rembourser.
  - Art. 11 : 2 taux selon que le membre verse les intérêts au comptant
    (RENEWAL_CASH ≈ 10 %) ou les reporte (RENEWAL_DEFERRED ≈ 15 %).
  - Art. 10 : la reconduction n'est possible qu'une seule fois par crédit
    (``issu_reconduction = True`` empêche la 2ᵉ).
  - Interaction CH-11 : la reconduction d'un crédit en mode 'source' produit
    un nouveau crédit en mode 'echeances' (le membre ne touche rien à la
    reconduction, donc pas de retenue à la source).
  - L'audit ``loan_renewal.approved`` capture la formule complète
    (capital_restant, intérêts_restants, intérêts_reconduction).

Ce module est un AUDIT — il assert chaque invariant explicitement plutôt
que de vérifier des bouts éclatés. Si une régression future change la
formule, ces tests cassent.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import Group

from apps_coop.audit.models import AppSetting, AuditLog
from apps_coop.loans.models import LoanRequest
from apps_coop.loans.services import (
    approve_loan_renewal,
    approve_loan_request,
    request_loan_renewal,
)
from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_factory_sequences():
    MemberFactory.reset_sequence(940000)
    UserFactory.reset_sequence(940000)
    yield


@pytest.fixture
def comite_user(db):
    u = User.objects.create_user(
        email="comite-ch10@gathe.test", password="x", username="comite-ch10",
    )
    g, _ = Group.objects.get_or_create(name="comite")
    u.groups.add(g)
    return u


def _set_setting(key: str, value: str):
    AppSetting.objects.update_or_create(
        cle=key, defaults={"valeur": value, "description": ""}
    )


def _enable_source_mode(enabled: bool = True):
    _set_setting("loans.interest_withheld_at_source", "true" if enabled else "false")


def _approve_initial(member, comite_user, *, montant=Decimal("100000")):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Prêt initial CH-10",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
        modalite_paiement="mensuel",
    )
    return approve_loan_request(
        lr,
        decided_by=comite_user,
        taux_annuel=Decimal("0.10"),
        date_premiere_echeance=date.today() + timedelta(days=30),
    )


def _request_renewal(loan, *, interets_au_comptant=False, duree=1):
    renewal = request_loan_renewal(
        loan,
        nouvelle_duree_mois=duree,
        interets_au_comptant=interets_au_comptant,
    )
    # Option « au comptant » = le membre verse les intérêts avant la décision.
    # (Le versement reste possible après : il n'est jamais bloquant.)
    if interets_au_comptant:
        _settle_interest(renewal)
    return renewal


def _settle_interest(renewal):
    """Constate l'encaissement des intérêts (canal agence simulé)."""
    from apps_coop.loans.renewal_payment_services import mark_renewal_interest_paid
    from apps_coop.payments.models import Payment

    payment = Payment.objects.create(
        member=renewal.loan.member,
        montant=renewal.interets_dus,
        type=Payment.Type.FRAIS_RECONDUCTION,
        source=Payment.Source.MANUEL,
        statut=Payment.Statut.VALIDE,
        date_versement=timezone.now(),
        date_validation=timezone.now(),
    )
    return mark_renewal_interest_paid(renewal, payment)


# ---------------------------------------------------------------------------
# 1. Article 11 — Intérêts × capital_restant (jamais × montant initial).
# ---------------------------------------------------------------------------
class TestArticle11InterestOnRemainingCapital:
    def test_au_comptant_uses_remaining_capital(self, active_member, comite_user):
        """100k initial → 0 remboursé → capital_restant = 100k → intérêts = 10k."""
        _enable_source_mode(False)  # Mode echeances pour assertions précises
        loan = _approve_initial(active_member, comite_user)
        renewal = _request_renewal(loan, interets_au_comptant=True)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Reste à remettre = 100k de capital + 10k d'intérêts = 110k.
        # Intérêts de reconduction = 10 % × 110k = 11k, DÉJÀ versés au
        # comptant → le nouveau dossier ne porte que les 110k.
        assert nouveau.montant == Decimal("110000.00")
        assert nouveau.montant_total_du == Decimal("110000.00")
        assert renewal.interets_dus == Decimal("11000.00")

    def test_deferred_uses_remaining_capital(self, active_member, comite_user):
        """Mode reporté = 15 % × capital_restant."""
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        renewal = _request_renewal(loan, interets_au_comptant=False)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.15"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Base à reconduire = 110k → 15 % × 110k = 16,5k. Non versés au
        # comptant, ils sont reportés → total 126,5k.
        assert nouveau.montant_total_du == Decimal("126500.00")

    def test_interest_calc_does_not_use_initial_amount(
        self, active_member, comite_user
    ):
        """Régression : si on payait 50% du crédit, l'intérêt de reconduction
        DOIT diminuer de moitié (porte sur le restant, pas l'initial)."""
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        # Règle 2026 « échéance unique » : le crédit n'a qu'une seule échéance
        # portant tout le capital. Pour laisser ≈ 50 % du capital dû, on règle
        # la MOITIÉ du montant total (l'imputation est proratisée capital/intérêt
        # dans ``_remaining_capital_and_interest`` → capital_restant = capital/2).
        inst = loan.installments.get()
        inst.montant_paye = (Decimal(inst.montant_total) / 2).quantize(Decimal("0.01"))
        inst.statut = "partielle"
        inst.save(update_fields=["montant_paye", "statut", "updated_at"])

        renewal = _request_renewal(loan, interets_au_comptant=True)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Moitié réglée → reste ≈ 50k de capital + 5k d'intérêts = 55k de
        # base → intérêts reconduction ≈ 5,5k. Si on utilisait par erreur le
        # montant initial (100k+10k), on serait à 11k.
        audit = AuditLog.objects.filter(
            action="loan_renewal.approved", entite_id=renewal.id
        ).latest("created_at")
        interets_reconduction = Decimal(audit.details_json["interets_reconduction"])
        # Tolérance d'arrondi : doit être ≈ 5,5k, certainement < 6k.
        assert interets_reconduction < Decimal("6000"), (
            f"Intérêts reconduction {interets_reconduction} suspect — devrait "
            f"être ~5,5k, pas 11k. Vérifie qu'on part bien du reste à remettre."
        )


# ---------------------------------------------------------------------------
# 2. Article 10 — Reconduction unique.
# ---------------------------------------------------------------------------
class TestArticle10SingleRenewal:
    def test_renewed_loan_marked_issu_reconduction(
        self, active_member, comite_user
    ):
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        renewal = _request_renewal(loan)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        assert nouveau.issu_reconduction is True

    def test_second_renewal_refused(self, active_member, comite_user):
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        renewal = _request_renewal(loan)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # Tentative de re-reconduction sur le nouveau crédit → erreur.
        with pytest.raises(ValueError, match="reconduction|reconduit"):
            request_loan_renewal(
                nouveau,
                nouvelle_duree_mois=1,
                interets_au_comptant=False,
            )


# ---------------------------------------------------------------------------
# 3. Interaction CH-10 × CH-11 — Reconduction en mode source.
# ---------------------------------------------------------------------------
class TestRenewalUnderSourceMode:
    def test_renewed_loan_stays_in_echeances_mode(
        self, active_member, comite_user
    ):
        """Le membre ne touche rien à la reconduction — pas de retenue source.
        Le nouveau Loan est figé en mode 'echeances' même si l'AppSetting
        source est activé globalement."""
        _enable_source_mode(True)
        loan = _approve_initial(active_member, comite_user)
        assert loan.mode_retenue_interets == "source"  # Loan initial en source

        renewal = _request_renewal(loan, interets_au_comptant=True)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        nouveau.refresh_from_db()
        # Le nouveau crédit est en mode echeances (CH-10/11 commentaire explicite).
        assert nouveau.mode_retenue_interets == "echeances"
        # interets_retenus_source = 0 (pas de retenue à la reconduction).
        assert nouveau.interets_retenus_source == Decimal("0")

    def test_renewal_of_source_loan_capital_restant_correct(
        self, active_member, comite_user
    ):
        """Loan en mode source → installments = capital pur → capital_restant
        = somme des capital non payés. Vérifie qu'on ne perd pas d'argent."""
        _enable_source_mode(True)
        loan = _approve_initial(active_member, comite_user)
        # Mode source : montant_total_du = 90k (net), pas 100k.
        assert loan.montant_total_du == Decimal("90000.00")

        renewal = _request_renewal(loan, interets_au_comptant=True)
        nouveau = approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        # capital_restant = 90k (rien remboursé). Pas d'intérêts restants
        # (échéances source = capital pur). Base = 90k. Les 9k d'intérêts de
        # reconduction ont été versés au comptant → total = base = 90k.
        assert nouveau.montant == Decimal("90000.00")
        assert nouveau.montant_total_du == Decimal("90000.00")
        assert renewal.interets_dus == Decimal("9000.00")


# ---------------------------------------------------------------------------
# 4. Audit — formule capturée.
# ---------------------------------------------------------------------------
class TestAuditCapturesFormula:
    def test_audit_records_capital_restant_and_interets(
        self, active_member, comite_user
    ):
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        renewal = _request_renewal(loan, interets_au_comptant=True)
        approve_loan_renewal(
            renewal,
            decided_by=comite_user,
            taux_annuel=Decimal("0.10"),
            date_premiere_echeance=date.today() + timedelta(days=30),
        )
        audit = AuditLog.objects.filter(
            action="loan_renewal.approved",
            entite_id=renewal.id,
        ).latest("created_at")
        details = audit.details_json
        assert Decimal(details["capital_restant"]) == Decimal("100000.00")
        assert Decimal(details["interets_restants"]) == Decimal("10000.00")
        # 10 % × (100k capital + 10k intérêts restants) = 11k.
        assert Decimal(details["interets_reconduction"]) == Decimal("11000.00")
        assert Decimal(details["taux_annuel"]) == Decimal("0.10")


# ---------------------------------------------------------------------------
# 5. Garde-fou — pas de reconduction sur crédit déjà soldé.
# ---------------------------------------------------------------------------
class TestNoRenewalOnSettledLoan:
    def test_renewal_rejected_when_capital_restant_zero(
        self, active_member, comite_user
    ):
        _enable_source_mode(False)
        loan = _approve_initial(active_member, comite_user)
        # Solde toutes les échéances → capital_restant = 0.
        for inst in loan.installments.all():
            inst.montant_paye = inst.montant_total
            inst.statut = "payee"
            inst.save(update_fields=["montant_paye", "statut", "updated_at"])

        renewal = _request_renewal(loan, interets_au_comptant=True)
        with pytest.raises(ValueError, match="[Cc]apital restant"):
            approve_loan_renewal(
                renewal,
                decided_by=comite_user,
                taux_annuel=Decimal("0.10"),
                date_premiere_echeance=date.today() + timedelta(days=30),
            )
