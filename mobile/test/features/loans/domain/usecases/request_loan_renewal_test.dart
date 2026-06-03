import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/features/loans/domain/repositories/loans_repository.dart';
import 'package:gathe_finance/features/loans/domain/usecases/request_loan_renewal.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements LoansRepository {}

void main() {
  late _MockRepo repo;
  late RequestLoanRenewal useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = RequestLoanRenewal(repo);
  });

  // Article 10 : la prorogation est fixe (+1 mois), pas de durée à valider.
  // Le membre choisit seulement le mode (Article 11).

  test('délègue au repo en mode comptant (10 %)', () async {
    final renewal = Fixtures.loanRenewal();
    when(() => repo.requestRenewal(loanId: 1, comptant: true))
        .thenAnswer((_) async => renewal);

    final result = await useCase.call(
      const RequestLoanRenewalParams(loanId: 1, comptant: true),
    );

    expect(result.id, renewal.id);
    verify(() => repo.requestRenewal(loanId: 1, comptant: true)).called(1);
  });

  test('délègue au repo en mode reporté (15 %)', () async {
    final renewal = Fixtures.loanRenewal();
    when(() => repo.requestRenewal(loanId: 1, comptant: false))
        .thenAnswer((_) async => renewal);

    await useCase.call(
      const RequestLoanRenewalParams(loanId: 1, comptant: false),
    );

    verify(() => repo.requestRenewal(loanId: 1, comptant: false)).called(1);
  });
}
