import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/usecases/usecase.dart';
import 'package:gathe_finance/features/onboarding/domain/repositories/onboarding_repository.dart';
import 'package:gathe_finance/features/onboarding/domain/usecases/onboarding_usecases.dart';
import 'package:mocktail/mocktail.dart';

class _MockRepo extends Mock implements OnboardingRepository {}

void main() {
  late _MockRepo repo;

  setUp(() => repo = _MockRepo());

  test('IsOnboardingSeen renvoie la valeur du repo', () async {
    when(() => repo.isSeen()).thenAnswer((_) async => true);
    expect(await IsOnboardingSeen(repo).call(const NoParams()), isTrue);
    when(() => repo.isSeen()).thenAnswer((_) async => false);
    expect(await IsOnboardingSeen(repo).call(const NoParams()), isFalse);
  });

  test('MarkOnboardingSeen délègue au repo', () async {
    when(() => repo.markSeen()).thenAnswer((_) async {});
    await MarkOnboardingSeen(repo).call(const NoParams());
    verify(() => repo.markSeen()).called(1);
  });

  test('ResetOnboarding délègue au repo', () async {
    when(() => repo.reset()).thenAnswer((_) async {});
    await ResetOnboarding(repo).call(const NoParams());
    verify(() => repo.reset()).called(1);
  });
}
