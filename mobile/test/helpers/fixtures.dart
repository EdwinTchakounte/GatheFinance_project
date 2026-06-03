import 'package:gathe_finance/features/auth/domain/entities/member.dart';
import 'package:gathe_finance/features/booklet/domain/entities/booklet_order.dart';
import 'package:gathe_finance/features/loans/domain/entities/eligibility.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_installment.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_renewal.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_request.dart';
import 'package:gathe_finance/features/notifications/domain/entities/app_notification.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_account.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_transaction.dart';

/// Fixtures partagées entre tous les tests — données canoniques.
class Fixtures {
  Fixtures._();

  static Member member() => Member(
        id: 1,
        numeroMembre: 'GF-2026-0001',
        prenom: 'Jean',
        nom: 'Kamga',
        email: 'jean.kamga@test.local',
        phone: '+237 6 99 11 22 33',
        statut: MemberStatus.actif,
        dateAdhesion: DateTime(2026, 3, 12),
      );

  static SavingsAccount savings({num solde = 365000}) => SavingsAccount(
        id: 1,
        solde: solde,
        dateOuverture: DateTime(2026, 3, 12),
        tauxInteret: 0.035,
        transactions: [
          SavingsTransaction(
            id: 1,
            type: SavingsType.depot,
            montant: solde,
            soldeApres: solde,
            date: DateTime(2026, 4, 1),
          ),
        ],
      );

  static Eligibility eligibilityOk() => const Eligibility(
        eligible: true,
        plafondMax: 3650000,
        soldeEpargne: 365000,
        ratioGarantie: 0.1,
        motifs: [],
      );

  static Eligibility eligibilityKo() => const Eligibility(
        eligible: false,
        plafondMax: 0,
        soldeEpargne: 365000,
        ratioGarantie: 0.1,
        motifs: ['Un crédit est déjà en cours.'],
      );

  static Loan loan({num soldeRestant = 420000}) => Loan(
        id: 1,
        numeroDossier: 'GF-CR-2026-0001',
        montant: 500000,
        tauxInteret: 0.12,
        dureeMois: 12,
        dateDecaissement: DateTime(2026, 3, 12),
        datePremiereEcheance: DateTime(2026, 4, 12),
        montantTotalDu: 560000,
        soldeRestant: soldeRestant,
        statut: LoanStatus.actif,
        installments: [
          LoanInstallment(
            id: 1,
            numero: 1,
            dateEcheance: DateTime(2026, 4, 12),
            montantCapital: 39667,
            montantInterets: 7000,
            montantTotal: 46667,
            montantPaye: 46667,
            statut: InstallmentStatus.payee,
          ),
          LoanInstallment(
            id: 2,
            numero: 2,
            dateEcheance: DateTime(2026, 5, 12),
            montantCapital: 39667,
            montantInterets: 7000,
            montantTotal: 46667,
            montantPaye: 0,
            statut: InstallmentStatus.aVenir,
          ),
        ],
      );

  static LoanRequestEntity loanRequest() => LoanRequestEntity(
        id: 100,
        montantDemande: 200000,
        dureeMois: 12,
        motif: 'Achat de matériel pour la boutique.',
        statut: LoanRequestStatus.enAttente,
        dateSoumission: DateTime(2026, 5, 1),
      );

  static LoanRenewalEntity loanRenewal() => LoanRenewalEntity(
        id: 200,
        loanId: 1,
        comptant: true,
        capitalRestant: 60000,
        interetsReconduction: 6000,
        statut: LoanRenewalStatus.demandee,
        dateDemande: DateTime(2026, 5, 1),
      );

  static BookletOrder bookletOrder() => BookletOrder(
        id: 1,
        statut: BookletStatus.payee,
        dateCommande: DateTime(2026, 5, 1),
        montant: 1000,
      );

  static List<AppNotification> notifications() => [
        AppNotification(
          id: 1,
          kind: NotifKind.savings,
          title: 'Dépôt confirmé',
          body: 'Test body',
          createdAt: DateTime(2026, 5, 16),
        ),
        AppNotification(
          id: 2,
          kind: NotifKind.loan,
          title: 'Lu',
          body: 'Déjà lu',
          createdAt: DateTime(2026, 5, 15),
          read: true,
        ),
      ];
}
