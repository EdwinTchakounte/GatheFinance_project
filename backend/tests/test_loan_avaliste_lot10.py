"""LOT 10 (refonte 2026) — Voie 2 AVALISTE (§7.2 BUSINESS_RULES_2026).

Couvre :
  - ``find_avaliste`` : numéro inconnu, nom mismatch, pas senior, suspendu, OK
  - Couverture suffisante / insuffisante (configurable via AppSetting)
  - ``request_avaliste_consent`` : LR → EN_ATTENTE_AVALISTE, snapshot soldes
  - Auto-désignation interdite (borrower == avaliste)
  - Double consent interdit sur la même LR
  - ``respond_to_avaliste_consent`` accept → LR.avaliste posée + EN_INSTRUCTION
  - Refus avec motif → REJETEE_AVALISTE + motif_rejet
  - Idempotence + non-rétractation (Q13)
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.loans.avaliste_services import (
    find_avaliste,
    request_avaliste_consent,
    respond_to_avaliste_consent,
)
from apps_coop.loans.models import AvalisteConsent, LoanRequest
from apps_coop.members.models import Member
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from tests.factories import MemberFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_senior(*, savings_collecte=Decimal("0"), savings_classique=Decimal("0")):
    """Crée un membre senior (date_adhesion > 12 mois) avec un solde donné."""
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=400))
    if savings_collecte > 0:
        sa = SavingsAccount.objects.get(member=m)
        sa.solde = savings_collecte
        sa.save(update_fields=["solde"])
    if savings_classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m,
            solde=savings_classique,
            date_ouverture=date.today(),
        )
    return m


def _make_new_member(*, savings_collecte=Decimal("0"), savings_classique=Decimal("0")):
    """Crée un membre récent (non senior)."""
    m = MemberFactory(date_adhesion=date.today() - timedelta(days=30))
    if savings_collecte > 0:
        sa = SavingsAccount.objects.get(member=m)
        sa.solde = savings_collecte
        sa.save(update_fields=["solde"])
    if savings_classique > 0:
        ClassicSavingsAccount.objects.create(
            member=m,
            solde=savings_classique,
            date_ouverture=date.today(),
        )
    return m


def _make_loan_request(member, *, montant=Decimal("50000")):
    return LoanRequest.objects.create(
        member=member,
        montant_demande=montant,
        duree_mois=3,
        motif="Test avaliste",
        statut=LoanRequest.Statut.EN_INSTRUCTION,
    )


# ---------------------------------------------------------------------------
# find_avaliste
# ---------------------------------------------------------------------------


class TestFindAvaliste:
    def test_numero_unknown_raises(self):
        with pytest.raises(LookupError):
            find_avaliste("GF-9999-9999", "Inexistant")

    def test_nom_mismatch_raises(self):
        senior = _make_senior()
        with pytest.raises(ValueError, match="nom de famille"):
            find_avaliste(senior.numero_membre, "MAUVAISNOM")

    def test_nom_case_insensitive_ok(self):
        senior = _make_senior()
        # Force un nom connu pour avoir un cas testable.
        senior.nom = "Dupont"
        senior.save(update_fields=["nom"])
        out = find_avaliste(senior.numero_membre, "DUPONT")
        assert out.pk == senior.pk

    def test_not_senior_raises(self):
        nm = _make_new_member()
        with pytest.raises(ValueError, match="ancienneté"):
            find_avaliste(nm.numero_membre, nm.nom)

    def test_not_active_raises(self):
        senior = _make_senior()
        senior.statut = Member.Statut.SUSPENDU
        senior.save(update_fields=["statut"])
        with pytest.raises(ValueError, match="n'est pas actif"):
            find_avaliste(senior.numero_membre, senior.nom)

    def test_empty_inputs_raises(self):
        with pytest.raises(ValueError, match="requis"):
            find_avaliste("", "")


# ---------------------------------------------------------------------------
# request_avaliste_consent
# ---------------------------------------------------------------------------


class TestRequestAvalisteConsent:
    def test_creates_consent_and_changes_lr_statut(self):
        # Réforme 2026 : la garantie est l'épargne CLASSIQUE (pas la collecte).
        borrower = _make_new_member(savings_classique=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("50000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))

        consent = request_avaliste_consent(
            lr,
            numero_identification=senior.numero_membre,
            nom=senior.nom,
        )
        assert consent.statut == AvalisteConsent.Statut.PENDING
        assert consent.avaliste_id == senior.id
        # Snapshot des épargnes DISPONIBLES : 10k borrower + 50k avaliste = 60k.
        assert consent.epargne_borrower_at_request == Decimal("10000")
        assert consent.epargne_avaliste_at_request == Decimal("50000")
        # Couverture = 60k / 50k = 1.2000.
        assert consent.couverture_ratio == Decimal("1.2000")
        # Gel : le demandeur gèle ses 10k, l'avaliste comble le manque (40k).
        assert consent.montant_caution == Decimal("40000")
        # LR a basculé + gel demandeur posé.
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_ATTENTE_AVALISTE
        assert lr.montant_gele_demandeur == Decimal("10000")
        # Avaliste pas encore posé sur la LR — il faut l'acceptation.
        assert lr.avaliste_id is None

    def test_borrower_cannot_be_own_avaliste(self):
        m = _make_senior(savings_collecte=Decimal("100000"))
        lr = _make_loan_request(m, montant=Decimal("50000"))
        with pytest.raises(ValueError, match="propre avaliste"):
            request_avaliste_consent(
                lr, numero_identification=m.numero_membre, nom=m.nom
            )

    def test_insufficient_coverage_rejects(self):
        # Borrower 5k + avaliste 10k = 15k, demande 50k → couverture 0.30, KO.
        borrower = _make_new_member(savings_collecte=Decimal("5000"))
        senior = _make_senior(savings_collecte=Decimal("10000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        with pytest.raises(ValueError, match="Couverture insuffisante"):
            request_avaliste_consent(
                lr, numero_identification=senior.numero_membre, nom=senior.nom
            )
        # LR statut inchangé.
        lr.refresh_from_db()
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION
        assert not AvalisteConsent.objects.filter(loan_request=lr).exists()

    def test_min_coverage_ratio_tunable(self):
        """Avec ratio=1.50, une couverture de 1.20 est insuffisante."""
        AppSetting.objects.update_or_create(
            cle="loans.avaliste.min_coverage_ratio",
            defaults={"valeur": "1.50"},
        )
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("50000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        with pytest.raises(ValueError, match="Couverture insuffisante"):
            request_avaliste_consent(
                lr, numero_identification=senior.numero_membre, nom=senior.nom
            )

    def test_already_has_consent_raises(self):
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        # Deuxième désignation refusée.
        senior2 = _make_senior(savings_classique=Decimal("100000"))
        with pytest.raises(ValueError, match="déjà un consentement"):
            request_avaliste_consent(
                lr, numero_identification=senior2.numero_membre, nom=senior2.nom
            )

    def test_identification_inputs_persisted(self):
        """Les chaînes saisies par le demandeur sont conservées brutes."""
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        senior.nom = "Mbappe"
        senior.save(update_fields=["nom"])
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom="  MBAPPE  "
        )
        # Le numéro est trim, le nom aussi (mais casse d'origine préservée).
        assert consent.identification_numero_saisi == senior.numero_membre
        assert consent.identification_nom_saisi == "MBAPPE"


# ---------------------------------------------------------------------------
# respond_to_avaliste_consent — accept
# ---------------------------------------------------------------------------


class TestRespondAccept:
    def test_accept_sets_lr_avaliste_and_en_instruction(self):
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(consent, accept=True)
        consent.refresh_from_db()
        lr.refresh_from_db()
        assert consent.statut == AvalisteConsent.Statut.ACCEPTED
        assert consent.responded_at is not None
        assert lr.avaliste_id == senior.id
        assert lr.statut == LoanRequest.Statut.EN_INSTRUCTION

    def test_double_accept_is_idempotent(self):
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(consent, accept=True)
        # Second accept : pas d'erreur.
        out = respond_to_avaliste_consent(consent, accept=True)
        assert out.statut == AvalisteConsent.Statut.ACCEPTED


# ---------------------------------------------------------------------------
# respond_to_avaliste_consent — refuse
# ---------------------------------------------------------------------------


class TestRespondRefuse:
    def test_refuse_sets_rejetee_avaliste_terminal(self):
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(
            consent, accept=False, motif="Trop risqué"
        )
        consent.refresh_from_db()
        lr.refresh_from_db()
        assert consent.statut == AvalisteConsent.Statut.REFUSED
        assert consent.refus_motif == "Trop risqué"
        assert lr.statut == LoanRequest.Statut.REJETEE_AVALISTE
        # motif_rejet alimenté pour traçabilité côté LR.
        assert "risqué" in lr.motif_rejet.lower()

    def test_refuse_without_motif_ok(self):
        """Le motif est facultatif (vs LenderConsentRequest qui l'exige)."""
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(consent, accept=False)
        consent.refresh_from_db()
        assert consent.statut == AvalisteConsent.Statut.REFUSED
        assert consent.refus_motif == ""

    def test_refuse_after_accept_raises_q13(self):
        """Rétractation après acceptation = interdit (Q13)."""
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(consent, accept=True)
        with pytest.raises(ValueError, match="Q13"):
            respond_to_avaliste_consent(consent, accept=False, motif="oups")

    def test_re_refuse_after_refuse_is_idempotent(self):
        borrower = _make_new_member(savings_collecte=Decimal("10000"))
        senior = _make_senior(savings_classique=Decimal("100000"))
        lr = _make_loan_request(borrower, montant=Decimal("50000"))
        consent = request_avaliste_consent(
            lr, numero_identification=senior.numero_membre, nom=senior.nom
        )
        respond_to_avaliste_consent(consent, accept=False, motif="non")
        out = respond_to_avaliste_consent(consent, accept=False, motif="non2")
        # Statut inchangé, motif initial préservé.
        assert out.statut == AvalisteConsent.Statut.REFUSED
        assert out.refus_motif == "non"
