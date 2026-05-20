import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/usecases/usecase.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_account.dart';
import 'package:gathe_finance/features/savings/domain/repositories/savings_repository.dart';
import 'package:gathe_finance/features/savings/domain/usecases/get_my_savings.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements SavingsRepository {}

void main() {
  late _MockRepo repo;
  late GetMySavings useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = GetMySavings(repo);
  });

  test('GetMySavings délègue au repository', () async {
    final acc = Fixtures.savings();
    when(() => repo.fetchMine()).thenAnswer((_) async => acc);
    final result = await useCase.call(const NoParams());
    expect(result, isA<SavingsAccount>());
    expect(result.solde, acc.solde);
  });
}
