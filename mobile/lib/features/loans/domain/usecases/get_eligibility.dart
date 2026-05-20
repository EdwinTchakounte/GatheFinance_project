import '../../../../core/usecases/usecase.dart';
import '../entities/eligibility.dart';
import '../repositories/loans_repository.dart';

class GetEligibility extends UseCase<Eligibility, NoParams> {
  const GetEligibility(this._repo);
  final LoansRepository _repo;

  @override
  Future<Eligibility> call(NoParams params) => _repo.eligibility();
}
