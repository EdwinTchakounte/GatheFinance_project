import '../../domain/entities/eligibility.dart';
import '../../domain/entities/lender_payout.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';

abstract class LoansRemoteDataSource {
  Future<List<Loan>> myActiveLoans();

  Future<List<LoanRequestEntity>> myRequests();

  Future<Eligibility> eligibility();

  /// CH-12 — Versements d'intérêts reçus en tant que prêteur (refonte §7.5).
  Future<List<LenderPayout>> myLenderPayouts();

  Future<LoanRequestSubmission> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    // CH-9 — Canal choisi par le membre. Optionnels pour rétro-compat.
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
  });

  /// CH-7 — Règle les frais d'étude (`frais_demande_credit`) via Mobile Money.
  /// Le backend identifie la LoanRequest EN_ATTENTE du membre côté webhook.
  Future<void> payStudyFee({
    required String phone,
    required String network,
  });

  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  });

  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  });
}
