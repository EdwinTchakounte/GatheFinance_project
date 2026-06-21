import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/booklet/domain/repositories/booklet_repository.dart';
import 'package:gathe_finance/features/booklet/domain/usecases/order_booklet.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements BookletRepository {}

void main() {
  late _MockRepo repo;
  late OrderBooklet useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = OrderBooklet(repo);
  });

  test('refuse un numéro incomplet (< 8 chiffres)', () {
    expect(
      () => useCase.call(const OrderBookletParams(
        phone: '69911',
        network: 'MTN',
      ),),
      throwsA(isA<ValidationFailure>()
          .having((f) => f.field, 'field', 'phone'),),
    );
    verifyZeroInteractions(repo);
  });

  test('accepte un numéro avec espaces et délègue', () async {
    final order = Fixtures.bookletOrder();
    when(() => repo.order(
          phone: '699 11 22 33',
          network: 'MTN',
        ),).thenAnswer((_) async => order);

    final result = await useCase.call(const OrderBookletParams(
      phone: '699 11 22 33',
      network: 'MTN',
    ),);

    expect(result, order);
  });
}
