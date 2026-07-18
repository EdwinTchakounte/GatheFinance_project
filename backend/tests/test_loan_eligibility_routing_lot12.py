"""Tests LOT 12 — Routeur d'éligibilité 3 voies (refonte 2026 §7.1).

Couvre :
  * détection automatique SENIOR_BRC / AVALISTE / CAMPAIGN
  * priorité de la première voie qui matche (tunable)
  * kill-switches par voie (libre arbitre admin)
  * tunable ``loans.eligibility.route_priority`` réorganisable
  * rejet auto avec motifs cumulés quand aucune voie ne s'applique
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps_coop.audit.models import AppSetting
from apps_coop.loans.eligibility_routing import (
    EligibilityRoute,
    evaluate_routes,
)
from apps_coop.loans.models import MicrocreditCampaign
from apps_coop.members.models import Member

from tests.factories import MemberFactory, UserFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setting(key: str, value: str):
    AppSetting.objects.update_or_create(cle=key, defaults={"valeur": value})


def _ancient_brc(member: Member, *, months_ago=18, brc=True) -> Member:
    """Marque le membre comme Ancien BRC (Voie 1 OK)."""
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = brc
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _new_member(member: Member, *, months_ago=2) -> Member:
    """Marque le membre comme nouvel adhérent (pas senior)."""
    member.date_adhesion = date.today() - timedelta(days=30 * months_ago)
    member.is_brc_member = False
    member.save(update_fields=["date_adhesion", "is_brc_member"])
    return member


def _add_savings(member: Member, amount: Decimal) -> None:
    """Alimente l'épargne CLASSIQUE du membre (= garantie, réforme 2026).

    La collecte journalière ne compte plus comme garantie : seule l'épargne
    classique (libre + placement) sert de couverture crédit.
    """
    from apps_coop.savings.models import ClassicSavingsAccount

    acc, _ = ClassicSavingsAccount.objects.get_or_create(
        member=member,
        defaults={"solde": Decimal("0"), "date_ouverture": date.today()},
    )
    acc.solde = amount
    acc.save(update_fields=["solde"])


def _make_campaign(**kw) -> MicrocreditCampaign:
    today = date.today()
    defaults = dict(
        nom="Campagne test",
        profil_cible="commercants",
        date_debut=today - timedelta(days=1),
        date_fin=today + timedelta(days=30),
        montant_min=Decimal("5000"),
        montant_max=Decimal("50000"),
        taux_interet=Decimal("0.10"),
        nb_jours_recouvrement=60,
        actif=True,
        created_by=UserFactory(),
    )
    defaults.update(kw)
    return MicrocreditCampaign.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Voie 1 — AUTO-COUVERTURE (ex-SENIOR_BRC) — réforme garantie 2026
# Matche dès que l'épargne classique disponible ≥ montant (sans avaliste).
# Plus d'exigence d'ancienneté ni de lien BRC.
# ---------------------------------------------------------------------------


class TestVoieSeniorBrc:
    def test_self_coverage_matches(self):
        # Nouvel adhérent (non senior) mais épargne classique ≥ montant :
        # auto-couverture l'emporte → pas besoin d'avaliste.
        m = _new_member(MemberFactory())
        _add_savings(m, Decimal("100000"))
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.eligible is True
        assert result.details["auto_couverture"] is True

    def test_insufficient_self_coverage_skips_voie1(self):
        m = _new_member(MemberFactory())
        _add_savings(m, Decimal("10000"))
        # Pas d'avaliste/campagne fournis → NONE.
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("couvrir soi-même" in motif for motif in result.motifs)

    def test_no_savings_skips_voie1(self):
        m = _new_member(MemberFactory())  # aucune épargne classique
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE

    def test_kill_switch_disables_voie1(self):
        _setting("loans.eligibility.allow_senior_brc", "false")
        m = _new_member(MemberFactory())
        _add_savings(m, Decimal("100000"))  # se couvrirait sinon
        result = evaluate_routes(m, montant=Decimal("100000"))
        # Voie auto-couverture désactivée → NONE.
        assert result.route == EligibilityRoute.NONE
        assert any("désactivée" in motif for motif in result.motifs)

    def test_exact_coverage_matches(self):
        # Épargne dispo == montant → couverture juste suffisante.
        m = _new_member(MemberFactory())
        _add_savings(m, Decimal("50000"))
        result = evaluate_routes(m, montant=Decimal("50000"))
        assert result.route == EligibilityRoute.SENIOR_BRC


# ---------------------------------------------------------------------------
# Voie 1 (chemin 2) — ANCIEN + BRC, sous-couverture jugée par le comité
# Un membre établi (ancienneté ≥ seuil) au statut BRC validé peut demander un
# crédit SANS avaliste et avec une épargne INFÉRIEURE : la demande passe en
# instruction, c'est le comité qui tranche.
# ---------------------------------------------------------------------------


class TestVoieAncienBrcSousCouverture:
    def test_ancient_brc_undercovered_matches(self):
        m = _ancient_brc(MemberFactory())  # senior + BRC
        _add_savings(m, Decimal("30000"))  # < montant
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.eligible is True
        assert result.details["senior_brc"] is True
        assert result.details["sous_couverture"] is True
        assert Decimal(result.details["manque"]) == Decimal("70000")

    def test_ancient_brc_no_savings_matches_full_manque(self):
        m = _ancient_brc(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert Decimal(result.details["manque"]) == Decimal("100000")

    def test_senior_without_brc_undercovered_rejected_by_default(self):
        # require_brc_for_senior = true (défaut) → l'ancienneté seule ne suffit pas.
        m = _ancient_brc(MemberFactory(), brc=False)
        _add_savings(m, Decimal("10000"))
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("BRC" in mo for mo in result.motifs)

    def test_senior_without_brc_matches_when_require_brc_false(self):
        _setting("loans.eligibility.require_brc_for_senior", "false")
        m = _ancient_brc(MemberFactory(), brc=False)
        _add_savings(m, Decimal("10000"))
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.details["sous_couverture"] is True

    def test_new_member_with_brc_flag_still_rejected_not_senior(self):
        # Nouvel adhérent (2 mois) même avec le flag BRC → pas "ancien".
        m = _new_member(MemberFactory(), months_ago=2)
        m.is_brc_member = True
        m.save(update_fields=["is_brc_member"])
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("Ancienneté insuffisante" in mo for mo in result.motifs)

    def test_auto_coverage_takes_precedence_over_senior_path(self):
        # Ancien + BRC MAIS couvert → chemin 1 (auto-couverture), pas sous-couverture.
        m = _ancient_brc(MemberFactory())
        _add_savings(m, Decimal("100000"))
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.details.get("auto_couverture") is True
        assert "sous_couverture" not in result.details


# ---------------------------------------------------------------------------
# Voie 2 — AVALISTE
# ---------------------------------------------------------------------------


class TestVoieAvaliste:
    def test_avaliste_with_coverage_matches(self):
        borrower = _new_member(MemberFactory())
        avaliste = _ancient_brc(MemberFactory(nom="DUPONT"))
        _add_savings(avaliste, Decimal("100000"))
        _add_savings(borrower, Decimal("10000"))
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom="DUPONT",
        )
        assert result.route == EligibilityRoute.AVALISTE
        assert result.details["avaliste_id"] == avaliste.id

    def test_avaliste_insufficient_coverage_skips(self):
        borrower = _new_member(MemberFactory())
        avaliste = _ancient_brc(MemberFactory(nom="DUPONT"))
        _add_savings(avaliste, Decimal("5000"))
        _add_savings(borrower, Decimal("1000"))
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom="DUPONT",
        )
        assert result.route == EligibilityRoute.NONE
        assert any("Couverture" in m for m in result.motifs)

    def test_avaliste_self_designation_rejected(self):
        borrower = _new_member(MemberFactory(nom="MARTIN"))
        _add_savings(borrower, Decimal("200000"))
        # Cas dégénéré : borrower passe d'abord par 'senior' mais comme il
        # est nouveau, on tombe sur l'avaliste où il tente de se désigner.
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            avaliste_numero=borrower.numero_membre,
            avaliste_nom="MARTIN",
        )
        # Le borrower n'est pas senior (find_avaliste rejette d'ailleurs
        # avant : `not_senior`), donc voie avaliste échoue. On vérifie juste
        # qu'il n'est pas matché en AVALISTE.
        assert result.route != EligibilityRoute.AVALISTE

    def test_kill_switch_disables_voie2(self):
        _setting("loans.eligibility.allow_avaliste", "false")
        borrower = _new_member(MemberFactory())
        avaliste = _ancient_brc(MemberFactory(nom="DUPONT"))
        _add_savings(avaliste, Decimal("200000"))
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom="DUPONT",
        )
        assert result.route == EligibilityRoute.NONE

    def test_no_avaliste_designation_skips_voie2(self):
        borrower = _new_member(MemberFactory())
        result = evaluate_routes(borrower, montant=Decimal("100000"))
        # Pas d'avaliste fourni → motif "non sollicitée"
        assert result.route == EligibilityRoute.NONE
        assert any("AVALISTE" in m for m in result.motifs)

    def test_invalid_avaliste_numero_skips_voie2(self):
        borrower = _new_member(MemberFactory())
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            avaliste_numero="GF-9999-9999",
            avaliste_nom="INCONNU",
        )
        assert result.route == EligibilityRoute.NONE


# ---------------------------------------------------------------------------
# Voie 3 — MICROCAMPAIGN
# ---------------------------------------------------------------------------


class TestVoieCampaign:
    def test_open_campaign_explicit_id_matches(self):
        borrower = _new_member(MemberFactory())
        c = _make_campaign()
        result = evaluate_routes(
            borrower,
            montant=Decimal("25000"),
            campaign_id=c.id,
        )
        assert result.route == EligibilityRoute.CAMPAIGN
        assert result.details["campaign_id"] == c.id

    def test_open_campaign_by_profil_cible(self):
        borrower = _new_member(MemberFactory())
        c = _make_campaign(profil_cible="agriculteurs")
        result = evaluate_routes(
            borrower,
            montant=Decimal("25000"),
            profil_cible="agriculteurs",
        )
        assert result.route == EligibilityRoute.CAMPAIGN
        assert result.details["campaign_id"] == c.id

    def test_amount_above_max_skips(self):
        borrower = _new_member(MemberFactory())
        _make_campaign(montant_max=Decimal("50000"))
        result = evaluate_routes(
            borrower,
            montant=Decimal("100000"),
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.NONE

    def test_closed_campaign_skips(self):
        borrower = _new_member(MemberFactory())
        _make_campaign(actif=False)
        result = evaluate_routes(
            borrower,
            montant=Decimal("25000"),
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.NONE

    def test_no_campaign_for_profil(self):
        borrower = _new_member(MemberFactory())
        _make_campaign(profil_cible="commercants")
        result = evaluate_routes(
            borrower,
            montant=Decimal("25000"),
            profil_cible="agriculteurs",
        )
        assert result.route == EligibilityRoute.NONE

    def test_kill_switch_disables_voie3(self):
        _setting("loans.eligibility.allow_campaign", "false")
        borrower = _new_member(MemberFactory())
        _make_campaign()
        result = evaluate_routes(
            borrower,
            montant=Decimal("25000"),
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.NONE

    def test_campaign_id_unknown_skips(self):
        borrower = _new_member(MemberFactory())
        result = evaluate_routes(
            borrower, montant=Decimal("25000"), campaign_id=99999
        )
        assert result.route == EligibilityRoute.NONE


# ---------------------------------------------------------------------------
# Priorité tunable + libre arbitre admin
# ---------------------------------------------------------------------------


class TestRoutePriority:
    def test_default_order_senior_first(self):
        """Si plusieurs voies matchent, SENIOR_BRC gagne par défaut."""
        m = _ancient_brc(MemberFactory())
        _add_savings(m, Decimal("25000"))  # auto-couverture OK
        c = _make_campaign()
        result = evaluate_routes(
            m,
            montant=Decimal("25000"),
            campaign_id=c.id,
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.SENIOR_BRC

    def test_admin_promotes_campaign(self):
        """Admin réordonne via AppSetting → CAMPAIGN passe en premier."""
        _setting(
            "loans.eligibility.route_priority",
            "campaign,senior_brc,avaliste",
        )
        m = _ancient_brc(MemberFactory())
        c = _make_campaign()
        result = evaluate_routes(
            m,
            montant=Decimal("25000"),
            campaign_id=c.id,
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.CAMPAIGN

    def test_admin_drops_voie_from_priority(self):
        """Voie absente de la priorité = désactivée même si allow_* = true."""
        _setting("loans.eligibility.route_priority", "avaliste,campaign")
        m = _ancient_brc(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        # SENIOR_BRC retiré de la priorité → tombe sur NONE (pas d'avaliste
        # ni de campagne).
        assert result.route == EligibilityRoute.NONE

    def test_malformed_priority_falls_back_default(self):
        """Priorité invalide → fallback ordre par défaut."""
        _setting("loans.eligibility.route_priority", "bogus,,xxx")
        m = _ancient_brc(MemberFactory())
        _add_savings(m, Decimal("100000"))  # auto-couverture OK
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC


# ---------------------------------------------------------------------------
# Rejet auto + motifs cumulés
# ---------------------------------------------------------------------------


class TestNoneCase:
    def test_new_member_no_avaliste_no_campaign_returns_none(self):
        m = _new_member(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert result.eligible is False
        # Doit avoir des motifs pour chaque voie évaluée.
        assert len(result.motifs) >= 2

    def test_motifs_prefixed_by_voie(self):
        m = _new_member(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert any(motif.startswith("[senior_brc]") for motif in result.motifs)
        assert any(motif.startswith("[avaliste]") for motif in result.motifs)
        assert any(motif.startswith("[campaign]") for motif in result.motifs)

    def test_zero_montant_is_invalid_for_avaliste(self):
        borrower = _new_member(MemberFactory())
        avaliste = _ancient_brc(MemberFactory(nom="DUPONT"))
        _add_savings(avaliste, Decimal("200000"))
        result = evaluate_routes(
            borrower,
            montant=Decimal("0"),
            avaliste_numero=avaliste.numero_membre,
            avaliste_nom="DUPONT",
        )
        assert result.route == EligibilityRoute.NONE
