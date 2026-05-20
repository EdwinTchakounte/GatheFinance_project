import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';

abstract class LoansRemoteDataSource {
  Future<List<Loan>> myActiveLoans();

  Future<List<LoanRequestEntity>> myRequests();

  Future<Eligibility> eligibility();

  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
  });

  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  });

  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required int nouvelleDureeMois,
  });
}
