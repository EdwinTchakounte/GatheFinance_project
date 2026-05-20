import '../../../../core/usecases/usecase.dart';
import '../entities/loan.dart';
import '../repositories/loans_repository.dart';

class GetMyActiveLoans extends UseCase<List<Loan>, NoParams> {
  const GetMyActiveLoans(this._repo);
  final LoansRepository _repo;

  @override
  Future<List<Loan>> call(NoParams params) => _repo.myActiveLoans();
}
