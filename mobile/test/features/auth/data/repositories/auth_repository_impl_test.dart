import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/auth/data/datasources/auth_remote_datasource.dart';
import 'package:gathe_finance/features/auth/data/repositories/auth_repository_impl.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRemote extends Mock implements AuthRemoteDataSource {}

void main() {
  late _MockRemote remote;
  late AuthRepositoryImpl repo;

  setUp(() {
    remote = _MockRemote();
    repo = AuthRepositoryImpl(remote);
  });

  group('signIn — traduction des exceptions techniques en Failures', () {
    test('CredentialsException → AuthFailure', () {
      when(() => remote.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          ),).thenThrow(const CredentialsException('bad'));
      expect(
        () => repo.signIn(email: 'a@b', password: 'x'),
        throwsA(isA<AuthFailure>()),
      );
    });

    test('NetworkException → NetworkFailure', () {
      when(() => remote.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          ),).thenThrow(const NetworkException());
      expect(
        () => repo.signIn(email: 'a@b', password: 'x'),
        throwsA(isA<NetworkFailure>()),
      );
    });

    test('ServerException → UnexpectedFailure', () {
      when(() => remote.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          ),).thenThrow(const ServerException('boom'));
      expect(
        () => repo.signIn(email: 'a@b', password: 'x'),
        throwsA(isA<UnexpectedFailure>()),
      );
    });

    test('Succès : renvoie le Member tel quel', () async {
      final m = Fixtures.member();
      when(() => remote.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          ),).thenAnswer((_) async => m);
      expect(await repo.signIn(email: 'a@b', password: 'x'), m);
    });
  });

  group('currentMember — mode hors-ligne', () {
    test('NetworkException → null (offline)', () async {
      when(() => remote.currentMember()).thenThrow(const NetworkException());
      expect(await repo.currentMember(), isNull);
    });
  });
}
