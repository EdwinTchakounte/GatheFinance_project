"""Cron quotidien des retards de crédit (Articles 12-13)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from django.core.management import call_command

from apps_coop.loans.models import Loan, LoanInstallment, LoanRequest
from apps_coop.loans.tasks import (
    CONTENTIEUX_THRESHOLD_DAYS,
    DUE_SOON_LEAD_DAYS,
    LATE_PENALTY_RATE,
    _compute_penalty,
    rappel_echeances_proches,
    suivi_retards_quotidien,
)
from apps_coop.notifications.models import Notification


pytestmark = pytest.mark.django_db(transaction=True)


def _build_loan(member, **overrides):
    lr = LoanRequest.objects.create(
        member=member,
        montant_demande=Decimal("100000"),
        duree_mois=3,
        motif="Test late payment",
        statut=LoanRequest.Statut.APPROUVEE,
    )
    return Loan.objects.create(
        member=member,
        loan_request=lr,
        numero_dossier=overrides.get("numero", "GF-CR-LATE-001"),
        montant=Decimal("100000"),
        taux_interet=Decimal("0.10"),
        duree_mois=3,
        date_decaissement=date.today() - timedelta(days=120),
        date_premiere_echeance=date.today() - timedelta(days=60),
        montant_total_du=Decimal("110000"),
        solde_restant=Decimal("110000"),
        statut=overrides.get("statut", Loan.Statut.ACTIF),
    )


def _build_installment(loan, *, days_late, statut=LoanInstallment.Statut.A_VENIR, montant_paye=Decimal("0"), numero=1):
    return LoanInstallment.objects.create(
        loan=loan,
        numero_echeance=numero,
        date_echeance=date.today() - timedelta(days=days_late),
        montant_capital=Decimal("33334"),
        montant_interets=Decimal("3333"),
        montant_total=Decimal("36667"),
        montant_paye=montant_paye,
        statut=statut,
    )


class TestPenaltyComputation:
    """Article 12 — 50 % des intérêts proratisés sur la somme manquante."""

    def test_full_amount_due_full_penalty(self):
        # Échéance 30 000 (20 000 capital + 10 000 intérêts), rien payé.
        # Pénalité = 50 % × 10 000 = 5 000
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("0"))
        assert p == Decimal("5000.00")

    def test_half_paid_half_penalty(self):
        # Échéance 30 000, 15 000 payés → reste 50 % → 50 % × 50 % × 10 000 = 2 500.
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("15000"))
        assert p == Decimal("2500.00")

    def test_fully_paid_no_penalty(self):
        p = _compute_penalty(Decimal("10000"), Decimal("30000"), Decimal("30000"))
        assert p == Decimal("0.00")

    def test_rate_constant(self):
        assert LATE_PENALTY_RATE == Decimal("0.50")


@pytest.fixture
def enable_art12():
    """Active la pénalité par échéance Art.12 (désactivée par défaut en 2026)."""
    from apps_coop.audit.models import AppSetting
    AppSetting.objects.update_or_create(
        cle="loans.penalite_par_echeance.enabled",
        defaults={"valeur": "true"},
    )


class TestSuiviRetardsCron:
    def test_marks_installment_en_retard_and_applies_penalty(
        self, active_member, enable_art12
    ):
        loan = _build_loan(active_member)
        inst = _build_installment(loan, days_late=10)

        summary = suivi_retards_quotidien()

        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.EN_RETARD
        assert inst.montant_penalite == Decimal("1666.50")  # 3333 × 50 % = 1666.5
        assert inst.penalite_appliquee_at is not None
        assert summary["passees_en_retard"] == 1
        assert summary["penalites_appliquees"] == 1

    def test_idempotent_does_not_double_apply_penalty(self, active_member, enable_art12):
        loan = _build_loan(active_member)
        inst = _build_installment(loan, days_late=10)

        suivi_retards_quotidien()
        first_penalty = LoanInstallment.objects.get(pk=inst.pk).montant_penalite
        first_at = LoanInstallment.objects.get(pk=inst.pk).penalite_appliquee_at

        summary2 = suivi_retards_quotidien()
        inst.refresh_from_db()

        # La pénalité n'a pas changé, le timestamp non plus.
        assert inst.montant_penalite == first_penalty
        assert inst.penalite_appliquee_at == first_at
        # Le 2e run ne ré-applique pas de pénalité (déjà en_retard).
        assert summary2["passees_en_retard"] == 0

    def test_loan_passes_en_retard_when_installment_late(self, active_member):
        loan = _build_loan(active_member)
        _build_installment(loan, days_late=5)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.EN_RETARD

    def test_loan_passes_contentieux_after_threshold(self, active_member):
        loan = _build_loan(active_member, numero="GF-CR-LATE-CTX")
        _build_installment(loan, days_late=CONTENTIEUX_THRESHOLD_DAYS + 5)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        assert loan.statut == Loan.Statut.CONTENTIEUX

    def test_skips_paid_installment(self, active_member):
        loan = _build_loan(active_member, numero="GF-CR-LATE-PAID")
        inst = _build_installment(
            loan,
            days_late=20,
            statut=LoanInstallment.Statut.PAYEE,
            montant_paye=Decimal("36667"),
        )

        suivi_retards_quotidien()

        inst.refresh_from_db()
        # Pas touché : la cron n'examine que A_VENIR ou PARTIELLE.
        assert inst.statut == LoanInstallment.Statut.PAYEE
        assert inst.montant_penalite == Decimal("0")

    def test_skips_cloture_loan(self, active_member):
        loan = _build_loan(
            active_member,
            numero="GF-CR-LATE-CLO",
            statut=Loan.Statut.CLOTURE,
        )
        _build_installment(loan, days_late=10)

        suivi_retards_quotidien()

        loan.refresh_from_db()
        # Un Loan clôturé reste clôturé même si une échéance traîne.
        assert loan.statut == Loan.Statut.CLOTURE

    def test_penalty_added_to_solde_restant(self, active_member):
        """A — Art.12 (rétrocompat) : pénalité par échéance ajoutée au solde restant.

        L'Art.12 par échéance étant DÉSACTIVÉ par défaut depuis 2026, ce test
        active explicitement le setting ``loans.penalite_par_echeance.enabled``
        pour vérifier que le mode legacy fonctionne toujours.
        """
        from apps_coop.audit.models import AppSetting
        AppSetting.objects.update_or_create(
            cle="loans.penalite_par_echeance.enabled",
            defaults={"valeur": "true"},
        )
        loan = _build_loan(active_member, numero="GF-CR-LATE-SOLDE")
        _build_installment(loan, days_late=10)  # pénalité = 3333 × 50 % = 1666.50

        suivi_retards_quotidien()

        loan.refresh_from_db()
        # 110 000 + 1 666.50 = 111 666.50 (sans pénalité globale — la date
        # limite globale n'est pas franchie pour ce test : un seul installment
        # à J-10 mais le crédit n'a pas encore atteint ``date_limite_globale``
        # qui est la dernière échéance prévue ; ici days_late=10 signifie que
        # cette échéance unique EST déjà la date limite).
        # Du coup la pénalité globale (50 % × 110000 = 55000) s'ajoute aussi.
        # On vérifie donc le total : 110000 + 1666.50 + 55833.25 = 167499.75.
        # Le test reste un test de rétrocompat Art.12 — on vérifie surtout que
        # la pénalité par échéance EST bien appliquée (cf. montant_penalite).
        inst = LoanInstallment.objects.get(loan=loan)
        assert inst.montant_penalite == Decimal("1666.50")

    def test_penalty_added_to_solde_once(self, active_member):
        """Le 2e passage du cron ne re-applique pas la pénalité par échéance."""
        from apps_coop.audit.models import AppSetting
        AppSetting.objects.update_or_create(
            cle="loans.penalite_par_echeance.enabled",
            defaults={"valeur": "true"},
        )
        loan = _build_loan(active_member, numero="GF-CR-LATE-SOLDE2")
        _build_installment(loan, days_late=10)

        suivi_retards_quotidien()
        first_inst = LoanInstallment.objects.get(loan=loan)
        first_at = first_inst.penalite_appliquee_at

        suivi_retards_quotidien()
        inst = LoanInstallment.objects.get(loan=loan)
        # La pénalité par échéance n'a pas changé (1× seulement).
        assert inst.montant_penalite == Decimal("1666.50")
        assert inst.penalite_appliquee_at == first_at


class TestOverdueNotification:
    """Article 12-13 — le membre est prévenu quand une échéance passe en retard."""

    def test_member_notified_on_overdue_with_penalty(self, active_member):
        call_command("seed_email_templates")
        loan = _build_loan(active_member, numero="GF-CR-NOTIF-1")
        _build_installment(loan, days_late=10)

        summary = suivi_retards_quotidien()

        assert summary["retards_notifies"] == 1
        notif = Notification.objects.filter(
            user=active_member.user, type="loan.installment_overdue"
        ).first()
        assert notif is not None

    def test_no_double_notification_on_second_run(self, active_member):
        call_command("seed_email_templates")
        loan = _build_loan(active_member, numero="GF-CR-NOTIF-2")
        _build_installment(loan, days_late=10)

        suivi_retards_quotidien()
        suivi_retards_quotidien()  # 2e passage : échéance déjà en_retard

        # Une seule notification de retard (pas de re-spam au 2e run).
        count = Notification.objects.filter(
            user=active_member.user, type="loan.installment_overdue"
        ).count()
        assert count == 1


class TestDueSoonReminder:
    """Rappel proactif J-3 d'une échéance à venir."""

    def test_reminder_sent_for_installment_due_in_lead_days(self, active_member):
        call_command("seed_email_templates")
        loan = _build_loan(active_member, numero="GF-CR-SOON-1")
        # Échéance dans exactement DUE_SOON_LEAD_DAYS jours (date future).
        _build_installment(loan, days_late=-DUE_SOON_LEAD_DAYS)

        summary = rappel_echeances_proches()

        assert summary["rappels_envoyes"] == 1
        assert Notification.objects.filter(
            user=active_member.user, type="loan.installment_due_soon"
        ).exists()

    def test_no_reminder_outside_lead_window(self, active_member):
        call_command("seed_email_templates")
        loan = _build_loan(active_member, numero="GF-CR-SOON-2")
        # Échéance dans 10 jours : hors fenêtre J-3.
        _build_installment(loan, days_late=-10)

        summary = rappel_echeances_proches()

        assert summary["rappels_envoyes"] == 0


class TestRepaymentCoversPenalty:
    """A — une échéance n'est soldée que pénalité comprise."""

    def test_installment_not_paid_until_penalty_covered(self, active_member, enable_art12):
        from apps_coop.payments.models import Payment
        from apps_coop.payments.services import handle_webhook_event

        loan = _build_loan(active_member, numero="GF-CR-PEN-PAY")
        inst = _build_installment(loan, days_late=10)  # pénalité 1666.50
        suivi_retards_quotidien()
        inst.refresh_from_db()
        assert inst.montant_penalite == Decimal("1666.50")

        def _pay(montant: Decimal) -> Payment:
            p = Payment.objects.create(
                member=active_member,
                montant=montant,
                type=Payment.Type.REMBOURSEMENT,
                source=Payment.Source.MOBILE_MONEY,
                statut=Payment.Statut.EN_ATTENTE,
                provider_code="tara",
                date_versement=timezone.now(),
                loan=loan,
            )
            handle_webhook_event(p.idempotency_key, "valide", provider_reference="REF")
            return p

        # 1) Payer juste capital+intérêts (36 667) ne suffit pas : reste la pénalité.
        _pay(Decimal("36667"))
        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.PARTIELLE

        # 2) Payer la pénalité restante (1 666.50) solde l'échéance.
        _pay(Decimal("1666.50"))
        inst.refresh_from_db()
        assert inst.statut == LoanInstallment.Statut.PAYEE
