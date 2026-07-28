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
        _add_savings(m, Decimal("10000"))  # 10 % < apport requis (30 %)
        # Pas d'avaliste/campagne fournis, apport insuffisant → NONE.
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("apport" in motif.lower() for motif in result.motifs)

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
# Voie 1 — G4 : PLANCHER 30 % OBLIGATOIRE POUR TOUS
# La souplesse « ancien sous-couvert » (ancien chemin 2) a été RETIRÉE : un
# membre (ancien ou non) avec moins de 30 % d'apport est INÉLIGIBLE. Le découvert
# est accordé par le COMITÉ à la validation (privilège tracé), pas à l'entrée.
# ---------------------------------------------------------------------------


class TestPlancher30PourTous:
    def test_ancien_sous_30pct_desormais_ineligible(self):
        m = _ancient_brc(MemberFactory())  # senior + BRC MAIS < 30 %
        _add_savings(m, Decimal("10000"))  # 10 %
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("apport" in mo.lower() for mo in result.motifs)

    def test_ancien_sans_epargne_ineligible(self):
        m = _ancient_brc(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE

    def test_ancien_avec_30pct_eligible(self):
        m = _ancient_brc(MemberFactory())
        _add_savings(m, Decimal("30000"))  # 30 % → apport suffisant
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.SENIOR_BRC
        assert result.eligible is True
        assert result.details.get("apport_couverture") is True

    def test_nouveau_membre_sous_30pct_ineligible(self):
        m = _new_member(MemberFactory(), months_ago=2)
        _add_savings(m, Decimal("10000"))
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any("apport" in mo.lower() for mo in result.motifs)

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

    def test_no_designation_defaults_to_senior_brc(self):
        # Sans désignation → voie par défaut SENIOR_BRC (choix implicite). Un
        # nouvel adhérent ni couvert ni ancien → NONE avec les motifs de CETTE
        # voie (l'avaliste n'est plus « évalué puis écarté »).
        borrower = _new_member(MemberFactory())
        result = evaluate_routes(borrower, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert any(m.startswith("[senior_brc]") for m in result.motifs)

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
    def test_explicit_campaign_choice_wins_over_senior(self):
        """Le CHOIX du membre prime : un ancien auto-couvert qui postule à une
        campagne (campaign_id fourni) est routé CAMPAIGN, pas SENIOR_BRC —
        fini le « je choisis campagne mais ancienneté s'affiche »."""
        m = _ancient_brc(MemberFactory())
        _add_savings(m, Decimal("25000"))  # auto-couverture OK, mais non retenue
        c = _make_campaign()
        result = evaluate_routes(
            m,
            montant=Decimal("25000"),
            campaign_id=c.id,
            profil_cible="commercants",
        )
        assert result.route == EligibilityRoute.CAMPAIGN

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
        # Motif de la voie choisie (senior_brc par défaut) — plancher apport 30 %.
        assert len(result.motifs) >= 1
        assert any("apport" in m.lower() for m in result.motifs)

    def test_motifs_prefixed_by_chosen_voie(self):
        # Seule la voie CHOISIE (ici SENIOR_BRC par défaut, aucune désignation)
        # est évaluée → tous les motifs portent SON préfixe, pas ceux des
        # autres voies (qui ne sont plus parcourues).
        m = _new_member(MemberFactory())
        result = evaluate_routes(m, montant=Decimal("100000"))
        assert result.route == EligibilityRoute.NONE
        assert result.motifs
        assert all(motif.startswith("[senior_brc]") for motif in result.motifs)

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
