"""Validation par SCÉNARIOS RÉELS — sortie globale lisible (livraison 2026-07-27).

But : jouer des cas concrets bout-en-bout sur le VRAI code (services + endpoints,
rien de mocké) et IMPRIMER l'état global à chaque étape, pour lire les vrais
chiffres de la gouvernance (gel 20 %, intérêt source, gagé/découvert, criticité,
exposition coop). Lancer avec :  pytest tests/test_scenario_reel_livraison.py -s -q
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from apps_coop.loans.avaliste_services import respond_to_avaliste_consent
from apps_coop.loans.criticality_services import credit_criticality_label
from apps_coop.loans.models import AvalisteConsent, Loan, LoanRequest
from apps_coop.loans.services import approve_loan_request, disburse_loan_manual
from apps_coop.loans.study_fee_services import pay_study_fee_from_savings
from apps_coop.loans.transfer_services import repay_loan_from_frozen
from apps_coop.payments.models import FeeType
from apps_coop.savings.models import ClassicSavingsAccount, SavingsAccount
from apps_coop.savings.services import classic_withdrawable
from apps_coop.loans.avaliste_services import member_frozen_guarantee
from tests.factories import MemberFactory, UserFactory

pytestmark = pytest.mark.django_db
User = get_user_model()
CREATE = "/api/v1/loans/requests/"
FUTURE = date.today() + timedelta(days=30)


def _fee(amount="1000"):
    FeeType.objects.update_or_create(
        code=FeeType.Code.DEMANDE_CREDIT,
        defaults={"libelle": "F", "montant": Decimal(amount), "actif": True},
    )


def _comite():
    n = User.objects.count()
    u = User.objects.create_user(
        username=f"sc-comite-{n}", email=f"sc-comite-{n}@t.test", password="x", is_staff=True
    )
    for g in ("comite", "coop_admin", "staff"):
        grp, _ = Group.objects.get_or_create(name=g)
        u.groups.add(grp)
    return u


def _api(m):
    c = APIClient()
    c.force_authenticate(user=m.user)
    return c


def _ancien(m, months=18):
    m.date_adhesion = date.today() - timedelta(days=30 * months)
    m.is_brc_member = True
    m.save(update_fields=["date_adhesion", "is_brc_member"])
    return m


def _classic(m, amount):
    ClassicSavingsAccount.objects.update_or_create(
        member=m, defaults={"solde": Decimal(amount), "date_ouverture": date.today()}
    )


def _f(x):
    return f"{int(Decimal(x)):,}".replace(",", " ")


def _patrimoine(m, titre):
    c = ClassicSavingsAccount.objects.filter(member=m).first()
    coll = SavingsAccount.objects.filter(member=m).first()
    solde = Decimal(c.solde) if c else Decimal(0)
    place = Decimal(c.solde_placement_actif) if c else Decimal(0)
    gel = member_frozen_guarantee(m)
    dispo = classic_withdrawable(c) if c else Decimal(0)
    print(f"    · Patrimoine {titre} : solde {_f(solde)} | placé {_f(place)} | "
          f"gelé {_f(gel)} | collecte {_f(coll.solde if coll else 0)} | "
          f"DISPO retrait {_f(dispo)}")


def _print_loan(loan, titre="Crédit"):
    print(f"    · {titre} #{loan.numero_dossier} : montant {_f(loan.montant)} | "
          f"décaissé NET {_f(loan.montant_decaisse_net)} | intérêt retenu "
          f"{_f(loan.interets_retenus_source)} | mode {loan.mode_retenue_interets}")
    print(f"        gagé {_f(loan.montant_gage)} | DÉCOUVERT {_f(loan.montant_decouvert)} | "
          f"criticité {credit_criticality_label(loan)} | privilège {loan.privilege_accorde}")


def _exposition_coop():
    from django.db.models import Sum
    tot = Loan.objects.filter(
        statut__in=[Loan.Statut.ACTIF, Loan.Statut.EN_RETARD]
    ).aggregate(s=Sum("montant_decouvert"))["s"] or Decimal(0)
    print(f"\n>>> EXPOSITION COOP au découvert (crédits actifs) : {_f(tot)} FCFA <<<")


# ---------------------------------------------------------------------------


def test_scenario_parcours_complet_membre():
    """LA LOGIQUE COMPLÈTE, bout-en-bout : un nouveau membre depuis l'adhésion
    jusqu'au remboursement de son crédit. On suit chaque étape et l'état global."""
    from apps_coop.members.services import approve_membership_request
    from apps_coop.payments.models import Payment
    from apps_coop.payments.services import handle_webhook_event
    from tests.factories import MembershipRequestFactory
    from django.utils import timezone

    print("\n" + "#" * 78)
    print("# PARCOURS COMPLET D'UN MEMBRE — de l'adhésion au remboursement du crédit")
    print("#" * 78)

    # Frais.
    for code, montant in (("ADHESION", "10000"), ("INSCRIPTION", "2000"), ("CARNET", "1000")):
        FeeType.objects.update_or_create(code=code, defaults={"libelle": code, "montant": Decimal(montant), "actif": True})
    _fee()  # frais d'étude crédit
    admin = _comite()

    # 1) Adhésion.
    req = MembershipRequestFactory(nom="MBALLA", prenom="Aïcha")
    m = approve_membership_request(req, instructed_by=admin, prenom="Aïcha", nom="MBALLA")
    m.date_adhesion = date.today() - timedelta(days=30 * 18)  # ancienneté pour le crédit plus tard
    m.save(update_fields=["date_adhesion"])
    print(f"\n[1. ADHÉSION] Demande approuvée → {m.nom_complet} créé, statut = {m.statut} (doit payer 3 frais).")

    # 2) Paiement des 3 frais → activation.
    def _pay_fee(t, mt):
        p = Payment.objects.create(member=m, montant=Decimal(mt), type=t, statut=Payment.Statut.EN_ATTENTE,
                                   source=Payment.Source.MOBILE_MONEY, provider_code="tara", date_versement=timezone.now())
        handle_webhook_event(p.idempotency_key, "valide", provider_reference=f"TX-{p.id}", raw_payload={})
    _pay_fee(Payment.Type.FRAIS_INSCRIPTION, "2000")
    _pay_fee(Payment.Type.FRAIS_CARNET, "1000")
    _pay_fee(Payment.Type.FRAIS_ADHESION, "10000")
    m.refresh_from_db()
    print(f"[2. ACTIVATION] 3 frais payés (13 000) → statut = {m.statut} · date_activation = {m.date_activation}")

    # 3) Épargne : le membre épargne 30 000 (au fil du temps).
    _classic(m, "30000")
    print("[3. ÉPARGNE] Le membre a épargné 30 000 en épargne classique.")
    _patrimoine(m, "membre")

    # 4) Crédit : il emprunte 100 000 (voie apport, 30 % détenus).
    r = _api(m).post(CREATE, {"montant_demande": "100000", "duree_mois": 6, "motif": "Fonds de commerce"}, format="json")
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    print(f"[4. DEMANDE CRÉDIT] 100 000 · voie {r.json()['route']} · apport GELÉ {_f(lr.montant_gele_demandeur)} (20 %)")
    pay_study_fee_from_savings(lr)
    lr.refresh_from_db()
    loan = approve_loan_request(lr, decided_by=admin, taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
    loan.refresh_from_db()
    print("[5. APPROBATION COMITÉ]")
    _print_loan(loan)
    disburse_loan_manual(loan, agent=admin, reference_externe="PC")
    loan.refresh_from_db()
    print(f"[6. DÉCAISSEMENT] Le membre reçoit {_f(loan.montant_decaisse_net)} (90 %). Reste dû : {_f(loan.solde_restant)}.")

    # 5) Remboursement via l'apport gelé.
    repay_loan_from_frozen(loan)
    loan.refresh_from_db()
    print(f"[7. REMBOURSEMENT] Transfert de l'apport gelé (20 000) → reste dû {_f(loan.solde_restant)} · statut {loan.statut}")
    _patrimoine(m, "fin de parcours")
    _exposition_coop()
    print("\n# FIN — le membre est passé d'inconnu à emprunteur, tout est cohérent.\n")


def test_scenario_credit_voie_apport():
    print("\n" + "=" * 78)
    print("SCÉNARIO 1 — Crédit voie APPORT (ancien, 30 % d'épargne, sans avaliste)")
    print("=" * 78)
    _fee()
    m = _ancien(MemberFactory())
    _classic(m, "30000")  # 30 % de 100 000
    print("[Étape 0] Membre ancien, épargne classique = 30 000 (30 % du montant visé)")
    _patrimoine(m, "avant")

    r = _api(m).post(CREATE, {"montant_demande": "100000", "duree_mois": 6, "motif": "Fonds de roulement"}, format="json")
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    print(f"[Étape 1] Demande créée — voie {r.json()['route']} | apport GELÉ = {_f(lr.montant_gele_demandeur)} (20 %)")
    _patrimoine(m, "après gel")

    pay_study_fee_from_savings(lr)
    lr.refresh_from_db()
    print(f"[Étape 2] Frais d'étude payés → statut {lr.statut}")

    loan = approve_loan_request(lr, decided_by=_comite(), taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
    loan.refresh_from_db()
    print("[Étape 3] Approuvé par le comité (mode source) :")
    _print_loan(loan)

    disburse_loan_manual(loan, agent=_comite(), reference_externe="SC1")
    loan.refresh_from_db()
    print(f"[Étape 4] Décaissé → le membre a reçu {_f(loan.montant_decaisse_net)} en main (90 %).")

    before = Decimal(loan.solde_restant)
    repay_loan_from_frozen(loan)
    loan.refresh_from_db()
    print(f"[Étape 5] Transfert de l'apport gelé (20 000) pour rembourser → "
          f"solde restant {_f(before)} → {_f(loan.solde_restant)} | statut {loan.statut}")
    _patrimoine(m, "après remb.")
    _exposition_coop()

    assert loan.montant_gage == Decimal("20000.00")
    assert loan.montant_decouvert == Decimal("80000.00")


def test_scenario_credit_voie_avaliste():
    print("\n" + "=" * 78)
    print("SCÉNARIO 2 — Crédit voie AVALISTE (demandeur 10 %, avaliste comble)")
    print("=" * 78)
    _fee()
    m = MemberFactory()
    _classic(m, "10000")
    av = _ancien(MemberFactory())
    _classic(av, "200000")
    print("[Étape 0] Demandeur épargne 10 000 ; avaliste (ancien) épargne 200 000")

    r = _api(m).post(CREATE, {
        "montant_demande": "100000", "duree_mois": 6, "motif": "Achat stock",
        "avaliste_numero": av.numero_membre, "avaliste_nom": av.nom,
    }, format="json")
    assert r.status_code == 201, r.content
    lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
    print(f"[Étape 1] Demande créée — voie {r.json()['route']}")

    pay_study_fee_from_savings(lr)
    from apps_coop.loans.study_fee_services import open_instruction_after_fees
    open_instruction_after_fees(lr)
    lr.refresh_from_db()
    consent = lr.avaliste_consent
    print(f"[Étape 2] Frais payés → avaliste sollicité | caution demandée = {_f(consent.montant_caution)}")
    respond_to_avaliste_consent(consent, accept=True)
    lr.refresh_from_db()
    print(f"[Étape 3] Avaliste ACCEPTE → statut {lr.statut}")

    loan = approve_loan_request(lr, decided_by=_comite(), taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
    loan.refresh_from_db()
    print("[Étape 4] Approuvé :")
    _print_loan(loan)
    _patrimoine(av, "AVALISTE (sa caution gelée)")
    _exposition_coop()

    assert loan.montant_decouvert == Decimal("0.00")  # couvert par apport + caution


def test_scenario_exposition_multi_credits():
    print("\n" + "=" * 78)
    print("SCÉNARIO 3 — Exposition coop avec plusieurs crédits à découvert")
    print("=" * 78)
    _fee()
    for i in range(3):
        m = _ancien(MemberFactory())
        _classic(m, "30000")
        r = _api(m).post(CREATE, {"montant_demande": "100000", "duree_mois": 6, "motif": f"credit {i}"}, format="json")
        lr = LoanRequest.objects.get(pk=r.json()["loan_request"]["id"])
        pay_study_fee_from_savings(lr)
        lr.refresh_from_db()
        loan = approve_loan_request(lr, decided_by=_comite(), taux_annuel=Decimal("0.10"), date_premiere_echeance=FUTURE)
        print(f"[Crédit {i+1}] découvert {_f(loan.montant_decouvert)} | criticité {credit_criticality_label(loan)}")
    _exposition_coop()
    print("    (3 × 80 000 = 240 000 d'exposition — palier d'alerte 2M non franchi)")
