import '../../../../core/usecases/usecase.dart';
import '../entities/lender_payout.dart';
import '../repositories/loans_repository.dart';

/// CH-12 — Lecture des versements d'intérêts reçus par le membre en tant
/// que prêteur (refonte 2026 §7.5 + Sinora §5.3 « si on prend une portion
/// de ton argent, tu seras notifié et bénéficieras d'un intérêt »).
class GetMyLenderPayouts extends UseCase<List<LenderPayout>, NoParams> {
  const GetMyLenderPayouts(this._repo);
  final LoansRepository _repo;

  @override
  Future<List<LenderPayout>> call(NoParams params) => _repo.myLenderPayouts();
}
