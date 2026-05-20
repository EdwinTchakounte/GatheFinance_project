import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/savings/domain/repositories/savings_repository.dart';
import 'package:gathe_finance/features/savings/domain/usecases/deposit_savings.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements SavingsRepository {}

void main() {
  late _MockRepo repo;
  late DepositSavings useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = DepositSavings(repo);
  });

  group('DepositSavings — validation domain', () {
    test('refuse un montant < 100 XAF (ValidationFailure)', () {
      expect(
        () => useCase.call(const DepositSavingsParams(
          amount: 50,
          phone: '699112233',
          network: 'MTN',
        )),
        throwsA(isA<ValidationFailure>()
            .having((f) => f.field, 'field', 'amount')),
      );
      verifyZeroInteractions(repo);
    });

    test('accepte le minimum (100 XAF) et délègue au repo', () async {
      final updated = Fixtures.savings(solde: 100);
      when(() => repo.deposit(
            amount: 100,
            phone: '699112233',
            network: 'MTN',
          )).thenAnswer((_) async => updated);

      final result = await useCase.call(const DepositSavingsParams(
        amount: 100,
        phone: '699112233',
        network: 'MTN',
      ));

      expect(result, updated);
      verify(() => repo.deposit(
            amount: 100,
            phone: '699112233',
            network: 'MTN',
          )).called(1);
    });

    test('propage les Failures du repo (ex. BusinessFailure)', () {
      when(() => repo.deposit(
            amount: any(named: 'amount'),
            phone: any(named: 'phone'),
            network: any(named: 'network'),
          )).thenThrow(const BusinessFailure('Compte suspendu'));

      expect(
        () => useCase.call(const DepositSavingsParams(
          amount: 5000,
          phone: '699112233',
          network: 'MTN',
        )),
        throwsA(isA<BusinessFailure>()),
      );
    });
  });
}
