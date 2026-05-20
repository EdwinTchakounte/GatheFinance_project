import '../../../../core/usecases/usecase.dart';
import '../repositories/onboarding_repository.dart';

class IsOnboardingSeen extends UseCase<bool, NoParams> {
  const IsOnboardingSeen(this._repo);
  final OnboardingRepository _repo;

  @override
  Future<bool> call(NoParams params) => _repo.isSeen();
}

class MarkOnboardingSeen extends UseCase<void, NoParams> {
  const MarkOnboardingSeen(this._repo);
  final OnboardingRepository _repo;

  @override
  Future<void> call(NoParams params) => _repo.markSeen();
}

class ResetOnboarding extends UseCase<void, NoParams> {
  const ResetOnboarding(this._repo);
  final OnboardingRepository _repo;

  @override
  Future<void> call(NoParams params) => _repo.reset();
}
