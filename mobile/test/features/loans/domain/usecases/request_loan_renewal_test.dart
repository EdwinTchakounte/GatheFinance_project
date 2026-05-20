import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
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

  test('refuse durée < 3 mois', () {
    expect(
      () => useCase.call(const RequestLoanRenewalParams(
        loanId: 1,
        nouvelleDureeMois: 2,
      )),
      throwsA(isA<ValidationFailure>()),
    );
    verifyZeroInteractions(repo);
  });

  test('refuse durée > 36 mois', () {
    expect(
      () => useCase.call(const RequestLoanRenewalParams(
        loanId: 1,
        nouvelleDureeMois: 40,
      )),
      throwsA(isA<ValidationFailure>()),
    );
  });

  test('délègue au repo pour une durée valide', () async {
    final renewal = Fixtures.loanRenewal();
    when(() => repo.requestRenewal(
          loanId: 1,
          nouvelleDureeMois: 6,
        )).thenAnswer((_) async => renewal);

    final result = await useCase.call(const RequestLoanRenewalParams(
      loanId: 1,
      nouvelleDureeMois: 6,
    ));

    expect(result.id, renewal.id);
    verify(() => repo.requestRenewal(loanId: 1, nouvelleDureeMois: 6))
        .called(1);
  });
}
