import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/loans/domain/repositories/loans_repository.dart';
import 'package:gathe_finance/features/loans/domain/usecases/make_loan_repayment.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements LoansRepository {}

void main() {
  late _MockRepo repo;
  late MakeLoanRepayment useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = MakeLoanRepayment(repo);
  });

  test('refuse montant < 100 XAF', () {
    expect(
      () => useCase.call(const MakeLoanRepaymentParams(
        loanId: 1,
        montant: 50,
        phone: '699112233',
        network: 'MTN',
      )),
      throwsA(isA<ValidationFailure>()
          .having((f) => f.field, 'field', 'montant')),
    );
    verifyZeroInteractions(repo);
  });

  test('délègue au repo et renvoie le Loan mis à jour', () async {
    final updated = Fixtures.loan(soldeRestant: 373333);
    when(() => repo.repay(
          loanId: 1,
          montant: 46667,
          phone: '699112233',
          network: 'MTN',
        )).thenAnswer((_) async => updated);

    final result = await useCase.call(const MakeLoanRepaymentParams(
      loanId: 1,
      montant: 46667,
      phone: '699112233',
      network: 'MTN',
    ));

    expect(result.soldeRestant, 373333);
  });
}
