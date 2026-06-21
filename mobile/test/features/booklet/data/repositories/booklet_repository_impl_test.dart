import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/booklet/data/datasources/booklet_remote_datasource.dart';
import 'package:gathe_finance/features/booklet/data/repositories/booklet_repository_impl.dart';
import 'package:mocktail/mocktail.dart';

class _MockRemote extends Mock implements BookletRemoteDataSource {}

void main() {
  late _MockRemote remote;
  late BookletRepositoryImpl repo;

  setUp(() {
    remote = _MockRemote();
    repo = BookletRepositoryImpl(remote);
  });

  test('myOrders — NetworkException → NetworkFailure', () {
    when(() => remote.myOrders()).thenThrow(const NetworkException());
    expect(() => repo.myOrders(), throwsA(isA<NetworkFailure>()));
  });

  test('order — ServerException 4xx → BusinessFailure', () {
    when(() => remote.order(
          phone: any(named: 'phone'),
          network: any(named: 'network'),
        ),).thenThrow(const ServerException('Bad', 422));
    expect(
      () => repo.order(phone: '699112233', network: 'MTN'),
      throwsA(isA<BusinessFailure>()),
    );
  });
}
