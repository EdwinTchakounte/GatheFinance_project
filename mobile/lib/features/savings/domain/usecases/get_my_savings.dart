import '../../../../core/usecases/usecase.dart';
import '../entities/savings_account.dart';
import '../repositories/savings_repository.dart';

class GetMySavings extends UseCase<SavingsAccount, NoParams> {
  const GetMySavings(this._repo);
  final SavingsRepository _repo;

  @override
  Future<SavingsAccount> call(NoParams params) => _repo.fetchMine();
}
