import '../../../../core/usecases/usecase.dart';
import '../entities/loan_request.dart';
import '../repositories/loans_repository.dart';

class GetMyLoanRequests extends UseCase<List<LoanRequestEntity>, NoParams> {
  const GetMyLoanRequests(this._repo);
  final LoansRepository _repo;

  @override
  Future<List<LoanRequestEntity>> call(NoParams params) => _repo.myRequests();
}
