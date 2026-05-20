import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/eligibility.dart';
import '../../domain/entities/loan.dart';
import '../../domain/entities/loan_renewal.dart';
import '../../domain/entities/loan_request.dart';
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
  Future<List<LoanRequestEntity>> myRequests() => _run(_remote.myRequests);

  @override
  Future<Eligibility> eligibility() => _run(_remote.eligibility);

  @override
  Future<LoanRequestEntity> submitRequest({
    required num montantDemande,
    required int dureeMois,
    required String motif,
  }) =>
      _run(() => _remote.submitRequest(
            montantDemande: montantDemande,
            dureeMois: dureeMois,
            motif: motif,
          ));

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
          ));

  @override
  Future<LoanRenewalEntity> requestRenewal({
    required int loanId,
    required int nouvelleDureeMois,
  }) =>
      _run(() => _remote.requestRenewal(
            loanId: loanId,
            nouvelleDureeMois: nouvelleDureeMois,
          ));
}
