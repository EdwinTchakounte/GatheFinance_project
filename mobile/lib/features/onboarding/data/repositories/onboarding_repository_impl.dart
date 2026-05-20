import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/repositories/onboarding_repository.dart';
import '../datasources/onboarding_local_datasource.dart';

class OnboardingRepositoryImpl implements OnboardingRepository {
  const OnboardingRepositoryImpl(this._local);
  final OnboardingLocalDataSource _local;

  @override
  Future<bool> isSeen() async {
    try {
      return await _local.isSeen();
    } on CacheException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<void> markSeen() => _local.markSeen();

  @override
  Future<void> reset() => _local.reset();
}
