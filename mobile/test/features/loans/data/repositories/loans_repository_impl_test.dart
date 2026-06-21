import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/loans/data/datasources/loans_remote_datasource.dart';
import 'package:gathe_finance/features/loans/data/repositories/loans_repository_impl.dart';
import 'package:mocktail/mocktail.dart';

class _MockRemote extends Mock implements LoansRemoteDataSource {}

void main() {
  late _MockRemote remote;
  late LoansRepositoryImpl repo;

  setUp(() {
    remote = _MockRemote();
    repo = LoansRepositoryImpl(remote);
  });

  group('myActiveLoans — codes HTTP traduits correctement', () {
    test('ServerException 4xx → BusinessFailure', () {
      when(() => remote.myActiveLoans())
          .thenThrow(const ServerException('Forbidden', 403));
      expect(() => repo.myActiveLoans(), throwsA(isA<BusinessFailure>()));
    });

    test('ServerException 5xx → UnexpectedFailure', () {
      when(() => remote.myActiveLoans())
          .thenThrow(const ServerException('Boom', 502));
      expect(() => repo.myActiveLoans(), throwsA(isA<UnexpectedFailure>()));
    });

    test('NetworkException → NetworkFailure', () {
      when(() => remote.myActiveLoans()).thenThrow(const NetworkException());
      expect(() => repo.myActiveLoans(), throwsA(isA<NetworkFailure>()));
    });
  });

  group('repay — traduction homogène', () {
    test('ServerException 400 → BusinessFailure', () {
      when(() => remote.repay(
            loanId: any(named: 'loanId'),
            montant: any(named: 'montant'),
            phone: any(named: 'phone'),
            network: any(named: 'network'),
          ),).thenThrow(const ServerException('Validation', 400));
      expect(
        () => repo.repay(
            loanId: 1, montant: 1000, phone: '6991', network: 'MTN',),
        throwsA(isA<BusinessFailure>()),
      );
    });
  });
}
