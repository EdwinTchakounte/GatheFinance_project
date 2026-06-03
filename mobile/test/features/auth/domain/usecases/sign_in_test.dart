import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/failures.dart';
import 'package:gathe_finance/features/auth/domain/repositories/auth_repository.dart';
import 'package:gathe_finance/features/auth/domain/usecases/sign_in.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements AuthRepository {}

void main() {
  late _MockRepo repo;
  late SignIn useCase;

  setUp(() {
    repo = _MockRepo();
    useCase = SignIn(repo);
  });

  group('SignIn', () {
    const params = SignInParams(email: 'jean@test.local', password: 'pwd1234');

    test('délègue au repository et renvoie le Member', () async {
      final member = Fixtures.member();
      when(() => repo.signIn(
            email: params.email,
            password: params.password,
          )).thenAnswer((_) async => member);

      final result = await useCase.call(params);

      expect(result, member);
      verify(() => repo.signIn(email: params.email, password: params.password))
          .called(1);
      verifyNoMoreInteractions(repo);
    });

    test('propage AuthFailure quand le repo refuse les credentials',
        () async {
      when(() => repo.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          )).thenThrow(const AuthFailure('bad creds'));

      expect(() => useCase.call(params), throwsA(isA<AuthFailure>()));
    });

    test('propage NetworkFailure si le réseau tombe', () async {
      when(() => repo.signIn(
            email: any(named: 'email'),
            password: any(named: 'password'),
          )).thenThrow(const NetworkFailure());

      expect(() => useCase.call(params), throwsA(isA<NetworkFailure>()));
    });
  });
}
