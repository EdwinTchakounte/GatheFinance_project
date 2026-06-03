"""LOT 8 (refonte 2026) — Funding state machine 24h (§7.3 BUSINESS_RULES_2026).

Couvre :
  - ``request_funding`` allocation first_fit / balanced + capacité insuffisante
  - Cas Mode A (global) vs Mode B (tranches explicites)
  - ``respond_to_consent_request`` (accept / refuse) + motif obligatoire
  - Auto-finalisation FUNDED dès qu'aucun PENDING ne reste (tous accepted)
  - Cron ``funding_window_expiry`` pose AUTO_ACCEPTED sur les expirés
  - Réallocation après un refus (vague 2 avec nouveaux prêteurs)
  - Réallocation impossible → ``EN_ATTENTE_FUNDING``
  - Vérifications : ``LenderAllocation`` posées, tranches → ENGAGEE,
    ``quote_part`` cohérente
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps_coop.audit.models import AppSetting
from apps_coop.loans.funding_services import (
    funding_window_expiry,
    request_funding,
    respond_to_consent_request,
)
from apps_coop.loans.models import (
    LenderAllocation,
    LenderConsentRequest,
    Loan,
    LoanFundingRequest,
    LoanRequest,
)
from apps_coop.savings.lender_services import add_tranche, opt_in_lender
from apps_coop.savings.models import (
    ClassicSavingsAccount,
    LenderTranche,
)
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _override_media_root(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_loan(borrower, montant=Decimal("100000"), suffix="A"):
    lr = LoanRequest.objects.create(
        member=borrower,
        montant_demande=montant,
        duree_mois=3,
        motif="Test funding",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=borrower,
        loan_request=lr,
        numero_dossier=f"GF-CR-{suffix}",
        montant=montant,
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today(),
        date_premiere_echeance=date.today() + timedelta(days=30),
        montant_total_du=montant * Decimal("1.10"),
        solde_restant=montant * Decimal("1.10"),
        statut=Loan.Statut.ACTIF,
    )


def _make_lender_mode_a(*, solde_classique: Decimal):
    """Crée un prêteur Mode A (global) avec un solde épargne classique."""
    lender = MemberFactory()
    ClassicSavingsAccount.objects.create(
        member=lender,
        solde=solde_classique,
        date_ouverture=date.today(),
    )
    opt_in_lender(member=lender, is_global=True)
    return lender


def _make_lender_mode_b(*, tranches: list[Decimal]):
    """Crée un prêteur Mode B avec une liste de tranches DISPONIBLE."""
    AppSetting.objects.update_or_create(
        cle="lender.tranche.min_amount",
        defaults={"valeur": "1000"},
    )
    lender = MemberFactory()
    opt_in_lender(member=lender, is_global=False)
    for montant in tranches:
        add_tranche(member=lender, montant=Decimal(montant))
    return lender


# ---------------------------------------------------------------------------
# request_funding — allocation initiale
# ---------------------------------------------------------------------------


class TestRequestFunding:
    def test_idempotent_returns_existing(self, active_member):
        loan = _build_loan(active_member, suffix="IDEMP")
        fr1 = request_funding(loan)
        fr2 = request_funding(loan)
        assert fr1.pk == fr2.pk

    def test_mode_a_single_lender_covers_full(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("50000"), suffix="MA1")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        assert fr.statut == LoanFundingRequest.Statut.PENDING
        crs = list(fr.consent_requests.all())
        assert len(crs) == 1
        assert crs[0].montant_propose == Decimal("50000")
        assert crs[0].tranche is None  # mode A → pas de tranche pré-existante

    def test_mode_a_first_fit_uses_biggest_first(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("80000"), suffix="MAFF")
        AppSetting.objects.update_or_create(
            cle="funding.allocation_strategy",
            defaults={"valeur": "first_fit"},
        )
        big = _make_lender_mode_a(solde_classique=Decimal("100000"))
        small = _make_lender_mode_a(solde_classique=Decimal("20000"))

        fr = request_funding(loan)
        crs = {cr.lender_id: cr for cr in fr.consent_requests.all()}
        # Le gros prêteur seul couvre les 80k → 1 seule consent_request.
        assert big.id in crs
        assert crs[big.id].montant_propose == Decimal("80000")
        assert small.id not in crs

    def test_mode_a_balanced_spreads(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="MABAL")
        AppSetting.objects.update_or_create(
            cle="funding.allocation_strategy",
            defaults={"valeur": "balanced"},
        )
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        small = _make_lender_mode_a(solde_classique=Decimal("20000"))

        fr = request_funding(loan)
        crs = list(fr.consent_requests.all())
        # Balanced commence par le plus petit → small (20k) puis complète avec big.
        assert len(crs) == 2
        montants = sorted([Decimal(c.montant_propose) for c in crs])
        assert montants == [Decimal("10000"), Decimal("20000")]
        # Le plus petit (small) est entièrement consommé en premier.
        small_cr = next(c for c in crs if c.lender_id == small.id)
        assert small_cr.montant_propose == Decimal("20000")

    def test_mode_b_consumes_tranches_in_order(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("25000"), suffix="MB1")
        lender = _make_lender_mode_b(tranches=[Decimal("10000"), Decimal("20000")])
        fr = request_funding(loan)
        crs = list(fr.consent_requests.all())
        # 2 consent_requests : 10k (tranche 1) + 15k (tranche 2 partielle).
        montants = sorted([Decimal(c.montant_propose) for c in crs])
        assert montants == [Decimal("10000"), Decimal("15000")]
        assert all(c.tranche is not None for c in crs)
        # Tranche pas encore engagée (PENDING).
        for t in LenderTranche.objects.filter(member=lender):
            assert t.statut == LenderTranche.Statut.DISPONIBLE

    def test_insufficient_capacity_creates_en_attente(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("100000"), suffix="EAF")
        _make_lender_mode_a(solde_classique=Decimal("30000"))
        fr = request_funding(loan)
        assert fr.statut == LoanFundingRequest.Statut.EN_ATTENTE_FUNDING
        # On a quand même crée la consent_request pour la partie couverte.
        assert fr.consent_requests.count() == 1


# ---------------------------------------------------------------------------
# respond_to_consent_request — réponse explicite + finalisation
# ---------------------------------------------------------------------------


class TestRespondConsent:
    def test_accept_explicit(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="ACC")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        respond_to_consent_request(consent_request=cr, accept=True)
        cr.refresh_from_db()
        assert cr.statut == LenderConsentRequest.Statut.ACCEPTED
        assert cr.responded_at is not None

    def test_refuse_requires_motif(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="REF")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        with pytest.raises(ValueError, match="motif est requis"):
            respond_to_consent_request(consent_request=cr, accept=False, motif="")

    def test_refuse_with_motif(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="REF2")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        respond_to_consent_request(
            consent_request=cr, accept=False, motif="Pas dispo"
        )
        cr.refresh_from_db()
        assert cr.statut == LenderConsentRequest.Statut.REFUSED
        assert cr.refus_motif == "Pas dispo"

    def test_response_idempotent_when_already_settled(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="IDP")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        respond_to_consent_request(consent_request=cr, accept=True)
        # Re-appel : pas d'erreur, statut inchangé.
        result = respond_to_consent_request(consent_request=cr, accept=False, motif="oups")
        assert result.statut == LenderConsentRequest.Statut.ACCEPTED

    def test_single_accept_finalizes_to_funded(self, active_member):
        """Quand le seul lender accepte, la FR doit basculer FUNDED."""
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="FUND1")
        lender = _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        respond_to_consent_request(consent_request=cr, accept=True)
        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.FUNDED
        assert fr.finalized_at is not None
        # Allocation posée.
        allocs = LenderAllocation.objects.filter(loan=loan)
        assert allocs.count() == 1
        alloc = allocs.first()
        assert alloc.lender_id == lender.id
        assert alloc.montant_alloue == Decimal("30000")
        assert alloc.quote_part == Decimal("1.00000000")
        # Tranche créée en ENGAGEE (mode A).
        assert alloc.tranche is not None
        assert alloc.tranche.statut == LenderTranche.Statut.ENGAGEE

    def test_mode_b_tranche_goes_to_engagee(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("10000"), suffix="MBF")
        lender = _make_lender_mode_b(tranches=[Decimal("10000")])
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        tranche_id = cr.tranche_id
        respond_to_consent_request(consent_request=cr, accept=True)
        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.FUNDED
        # Pas de nouvelle tranche créée — la même est passée en ENGAGEE.
        tranche = LenderTranche.objects.get(pk=tranche_id)
        assert tranche.statut == LenderTranche.Statut.ENGAGEE
        assert tranche.engaged_in_loan_id == loan.id


# ---------------------------------------------------------------------------
# Cron funding_window_expiry — tacit acceptance + réallocation
# ---------------------------------------------------------------------------


class TestFundingWindowExpiry:
    def test_auto_accepts_expired_pending(self, active_member):
        loan = _build_loan(active_member, montant=Decimal("20000"), suffix="EXP1")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        # Force la deadline dans le passé.
        past = timezone.now() - timedelta(hours=25)
        LenderConsentRequest.objects.filter(funding_request=fr).update(deadline=past)
        LoanFundingRequest.objects.filter(pk=fr.pk).update(deadline=past)

        result = funding_window_expiry()
        assert result["auto_accepted"] == 1
        assert result["settled"] == 1
        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.FUNDED

    def test_skips_when_pending_still_in_window(self, active_member):
        """Si la deadline est encore future, le cron ne touche pas la FR."""
        loan = _build_loan(active_member, montant=Decimal("20000"), suffix="WIND")
        _make_lender_mode_a(solde_classique=Decimal("100000"))
        request_funding(loan)
        result = funding_window_expiry()
        assert result["auto_accepted"] == 0
        assert result["settled"] == 0
        assert result["skipped"] == 1

    def test_reallocates_when_refused_and_replacement_exists(self, active_member):
        """Refus explicite → vague 2 avec un autre prêteur."""
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="REAL")
        AppSetting.objects.update_or_create(
            cle="funding.allocation_strategy",
            defaults={"valeur": "first_fit"},
        )
        primary = _make_lender_mode_a(solde_classique=Decimal("100000"))
        backup = _make_lender_mode_a(solde_classique=Decimal("100000"))

        fr = request_funding(loan)
        # Primary est sollicité (first_fit, capacité égale → premier vu).
        primary_cr = fr.consent_requests.first()
        primary_id_solicited = primary_cr.lender_id

        # Refus explicite déclenche le settle direct.
        respond_to_consent_request(
            consent_request=primary_cr, accept=False, motif="indispo"
        )
        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.REALLOCATING
        assert fr.wave_number == 2

        # Nouvelle consent_request pour le backup.
        new_crs = fr.consent_requests.filter(
            statut=LenderConsentRequest.Statut.PENDING
        )
        assert new_crs.count() == 1
        replacement = new_crs.first()
        assert replacement.lender_id != primary_id_solicited

    def test_exhausted_when_no_replacement(self, active_member):
        """Refus + pas de backup → EN_ATTENTE_FUNDING."""
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="EXH")
        only = _make_lender_mode_a(solde_classique=Decimal("100000"))
        fr = request_funding(loan)
        cr = fr.consent_requests.first()
        respond_to_consent_request(consent_request=cr, accept=False, motif="non")
        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.EN_ATTENTE_FUNDING

    def test_full_cycle_with_tacit_acceptance(self, active_member):
        """Scénario end-to-end : 2 prêteurs sollicités, 1 accepte, 1 silencieux."""
        loan = _build_loan(active_member, montant=Decimal("30000"), suffix="E2E")
        AppSetting.objects.update_or_create(
            cle="funding.allocation_strategy",
            defaults={"valeur": "balanced"},
        )
        l1 = _make_lender_mode_a(solde_classique=Decimal("20000"))
        l2 = _make_lender_mode_a(solde_classique=Decimal("50000"))

        fr = request_funding(loan)
        crs = list(fr.consent_requests.all())
        assert len(crs) == 2

        # L'un accepte explicitement
        respond_to_consent_request(consent_request=crs[0], accept=True)

        # L'autre laisse passer la fenêtre — on simule l'expiration.
        past = timezone.now() - timedelta(hours=25)
        LenderConsentRequest.objects.filter(pk=crs[1].pk).update(deadline=past)
        funding_window_expiry()

        fr.refresh_from_db()
        assert fr.statut == LoanFundingRequest.Statut.FUNDED
        # 2 allocations posées, sommes égales à 30k.
        allocs = LenderAllocation.objects.filter(loan=loan)
        total = sum(a.montant_alloue for a in allocs)
        assert total == Decimal("30000")
        # Toutes les tranches sont ENGAGEE.
        for a in allocs:
            assert a.tranche.statut == LenderTranche.Statut.ENGAGEE
