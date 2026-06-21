import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/savings/data/datasources/savings_remote_datasource.dart';
import 'package:gathe_finance/features/savings/data/repositories/savings_repository_impl.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRemote extends Mock implements SavingsRemoteDataSource {}

void main() {
  late _MockRemote remote;
  late SavingsRepositoryImpl repo;

  setUp(() {
    remote = _MockRemote();
    repo = SavingsRepositoryImpl(remote);
  });

  test('fetchMine — succès, snapshot transmis', () async {
    final account = Fixtures.savings();
    when(() => remote.fetchMine()).thenAnswer((_) async => account);
    expect((await repo.fetchMine()).solde, account.solde);
  });

  test('fetchMine — NetworkException → NetworkFailure', () {
    when(() => remote.fetchMine()).thenThrow(const NetworkException());
    expect(() => repo.fetchMine(), throwsA(isA<NetworkFailure>()));
  });

  test('deposit — ServerException → UnexpectedFailure', () {
    when(() => remote.deposit(
          amount: any(named: 'amount'),
          phone: any(named: 'phone'),
          network: any(named: 'network'),
        ),).thenThrow(const ServerException('Boom'));
    expect(
      () => repo.deposit(amount: 1000, phone: '6991', network: 'MTN'),
      throwsA(isA<UnexpectedFailure>()),
    );
  });
}
