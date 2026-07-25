import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/lender_payout.dart';
import '../../domain/entities/loan.dart';
import '../../../forms/domain/entities/form_schema.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
import '../../domain/entities/loan_request_submission.dart';
import '../../domain/repositories/loans_repository.dart';
import '../datasources/loans_remote_datasource.dart';

class LoansRepositoryImpl implements LoansRepository {
  const LoansRepositoryImpl(this._remote);
  final LoansRemoteDataSource _remote;

  Future<T> _run<T>(Future<T> Function() op) async {
    try {
      return await op();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      final code = e.statusCode ?? 500;
      if (code >= 400 && code < 500) {
        throw BusinessFailure(e.message);
      }
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<List<Loan>> myActiveLoans() => _run(_remote.myActiveLoans);

  @override
  Future<List<Loan>> myClosedLoans() => _run(_remote.myClosedLoans);

  @override
  Future<void> hideLoan(int loanId) => _run(() => _remote.hideLoan(loanId));

  @override
  Future<List<LoanRequestEntity>> myRequests() => _run(_remote.myRequests);

  @override
  Future<List<LenderPayout>> myLenderPayouts() =>
      _run(_remote.myLenderPayouts);

  @override
  Future<Eligibility> eligibility() => _run(_remote.eligibility);

  @override
  Future<LoanRequestSubmission> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
    LoanReceiveChannel? moyenReception,
    String? recipientPhone,
    Map<String, Object?> extraValues = const {},
  }) =>
      _run(() => _remote.submitRequest(
            montantDemande: montantDemande,
            dureeMois: dureeMois,
            motif: motif,
            moyenReception: moyenReception,
            recipientPhone: recipientPhone,
            extraValues: extraValues,
          ),);

  @override
  Future<void> payStudyFee({
    required String phone,
    required String network,
    int? montant,
  }) =>
      _run(() => _remote.payStudyFee(
            phone: phone,
            network: network,
            montant: montant,
          ),);

  @override
  Future<void> payStudyFeeFromSavings({required int requestId}) =>
      _run(() => _remote.payStudyFeeFromSavings(requestId: requestId));

  @override
  Future<void> respondCounterProposal({
    required int requestId,
    required bool accept,
    String? motif,
  }) =>
      _run(
        () => _remote.respondCounterProposal(
          requestId: requestId,
          accept: accept,
          motif: motif,
        ),
      );

  @override
  Future<FormSchema?> getActiveLoanRequestSchema() =>
      _run(_remote.getActiveLoanRequestSchema);

  @override
  Future<void> uploadLoanRequestAttachment({
    required int loanRequestId,
    required String schemaFieldId,
    required String filePath,
    required String fileName,
  }) =>
      _run(() => _remote.uploadLoanRequestAttachment(
            loanRequestId: loanRequestId,
            schemaFieldId: schemaFieldId,
            filePath: filePath,
            fileName: fileName,
          ),);

  @override
  Future<Loan> repay({
    required int loanId,
    required num montant,
    required String phone,
    required String network,
  }) =>
      _run(() => _remote.repay(
            loanId: loanId,
            montant: montant,
            phone: phone,
            network: network,
          ),);

  @override
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required bool comptant,
  }) =>
      _run(() => _remote.requestRenewal(
            loanId: loanId,
            comptant: comptant,
          ),);

  @override
  Future<LoanRenewalEntity> payRenewalInterestFromSavings(int renewalId) =>
      _run(() => _remote.payRenewalInterestFromSavings(renewalId));
}
