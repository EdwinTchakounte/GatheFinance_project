import '../entities/eligibility.dart';
import '../entities/loan.dart';
import '../entities/loan_renewal.dart';
import '../entities/loan_request.dart';

abstract class LoansRepository {
  /// Crédits en cours du membre (statut != cloture).
  Future<List<Loan>> myActiveLoans();

  /// Demandes de crédit du membre (toutes statuts confondus).
  Future<List<LoanRequestEntity>> myRequests();

  /// Vérification d'éligibilité à une **nouvelle** demande de crédit.
  Future<Eligibility> eligibility();

  /// Soumet une demande de crédit — renvoie la LoanRequest créée.
  /// Lève `ValidationFailure` / `BusinessFailure` côté domain.
  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
  });

  /// Effectue un remboursement d'échéance via Mobile Money.
  /// Renvoie le Loan mis à jour (solde restant, statut, échéances).
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  });

  /// Demande la reconduction d'un crédit en cours.
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required int nouvelleDureeMois,
  });
}
