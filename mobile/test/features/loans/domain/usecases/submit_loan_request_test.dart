import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_request_submission.dart';
import 'package:gathe_finance/features/loans/domain/repositories/loans_repository.dart';
import 'package:gathe_finance/features/loans/domain/usecases/submit_loan_request.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements LoansRepository {}

void main() {
  late _MockRepo repo;
  late SubmitLoanRequest useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = SubmitLoanRequest(repo);
  });

  group('SubmitLoanRequest — validation', () {
    test('refuse un montant < 50 000 XAF', () {
      expect(
        () => useCase.call(const SubmitLoanRequestParams(
          montantDemande: 40000,
          dureeMois: 3,
          motif: 'Achat outillage pro pour ma boutique',
        ),),
        throwsA(isA<ValidationFailure>()
            .having((f) => f.field, 'field', 'montant'),),
      );
    });

    test('refuse une durée < 2 mois (Art. 7 : plancher 2 mois)', () {
      expect(
        () => useCase.call(const SubmitLoanRequestParams(
          montantDemande: 200000,
          dureeMois: 1,
          motif: 'Achat outillage pro pour ma boutique',
        ),),
        throwsA(isA<ValidationFailure>()
            .having((f) => f.field, 'field', 'duree'),),
      );
    });

    test('accepte une durée = 2 mois (borne basse)', () async {
      final created = LoanRequestSubmission(request: Fixtures.loanRequest());
      when(() => repo.submitRequest(
            montantDemande: 200000,
            dureeMois: 2,
            motif: 'Achat outillage pro pour ma boutique',
          ),).thenAnswer((_) async => created);
      final result = await useCase.call(const SubmitLoanRequestParams(
        montantDemande: 200000,
        dureeMois: 2,
        motif: 'Achat outillage pro pour ma boutique',
      ),);
      expect(result, created);
    });

    test('refuse une durée > 9 mois (Art. 7 : plafond 9 mois)', () {
      expect(
        () => useCase.call(const SubmitLoanRequestParams(
          montantDemande: 200000,
          dureeMois: 10,
          motif: 'Achat outillage pro pour ma boutique',
        ),),
        throwsA(isA<ValidationFailure>()
            .having((f) => f.field, 'field', 'duree'),),
      );
    });

    test('refuse un motif < 10 caractères (trimé)', () {
      expect(
        () => useCase.call(const SubmitLoanRequestParams(
          montantDemande: 200000,
          dureeMois: 3,
          motif: '   short  ',
        ),),
        throwsA(isA<ValidationFailure>()
            .having((f) => f.field, 'field', 'motif'),),
      );
    });

    test('passe la validation et trim le motif avant le repo', () async {
      final created = LoanRequestSubmission(request: Fixtures.loanRequest());
      when(() => repo.submitRequest(
            montantDemande: 200000,
            dureeMois: 3,
            motif: 'Achat outillage pro',
          ),).thenAnswer((_) async => created);

      final result = await useCase.call(const SubmitLoanRequestParams(
        montantDemande: 200000,
        dureeMois: 3,
        motif: '  Achat outillage pro  ',
      ),);

      expect(result, created);
      verify(() => repo.submitRequest(
            montantDemande: 200000,
            dureeMois: 3,
            motif: 'Achat outillage pro',
          ),).called(1);
    });
  });
}
