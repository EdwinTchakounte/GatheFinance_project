import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/error/exceptions.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/auth/data/datasources/auth_dio_datasource.dart';
import 'package:gathe_finance/features/auth/domain/entities/member.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

const _validPayload = {
  'id': 7,
  'email': 'jean@coop.local',
  'first_name': 'Jean',
  'last_name': 'Kamga',
  'is_staff': false,
  'is_superuser': false,
  'groups': <String>[],
  'member': {
    'id': 21,
    'numero_membre': 'GF-2026-0021',
    'nom': 'Kamga',
    'prenom': 'Jean',
    'statut': 'actif',
    'phone': '+237 6 99 11 22 33',
    'date_adhesion': '2026-03-12',
  },
};

void main() {
  group('AuthDioDataSource — signIn', () {
    test('Succès : parse identité + membre (avec phone + date_adhesion)',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/auth/login/', method: 'POST', status: 200, body: _validPayload);
      final ds = AuthDioDataSource(_client(adapter));

      final member = await ds.signIn(
        email: 'jean@coop.local',
        password: 'test1234',
      );

      expect(member.id, 21); // id du Member backend (pas User.id)
      expect(member.email, 'jean@coop.local');
      expect(member.prenom, 'Jean');
      expect(member.statut, MemberStatus.actif);
      expect(member.phone, '+237 6 99 11 22 33');
      expect(member.dateAdhesion, DateTime(2026, 3, 12));
    });

    test('Compte sans member → ServerException', () async {
      final payload = Map<String, dynamic>.from(_validPayload)..['member'] = null;
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/auth/login/', method: 'POST', status: 200, body: payload);
      final ds = AuthDioDataSource(_client(adapter));

      expect(
        () => ds.signIn(email: 'x@x.com', password: 'y'),
        throwsA(isA<ServerException>()),
      );
    });

    test('401 → CredentialsException avec le detail', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/auth/login/',
            method: 'POST',
            status: 401,
            body: {'detail': 'Identifiants invalides.'});
      final ds = AuthDioDataSource(_client(adapter));

      expect(
        () => ds.signIn(email: 'x@x.com', password: 'y'),
        throwsA(
          isA<CredentialsException>().having(
            (e) => e.message,
            'message',
            'Identifiants invalides.',
          ),
        ),
      );
    });
  });

  group('AuthDioDataSource — currentMember', () {
    test('Session active → Member', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/me/', method: 'GET', status: 200, body: _validPayload);
      final ds = AuthDioDataSource(_client(adapter));
      final m = await ds.currentMember();
      expect(m, isNotNull);
      expect(m!.numeroMembre, 'GF-2026-0021');
    });

    test('401 → null (non connecté, pas une erreur)', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/me/',
            method: 'GET', status: 401, body: {'detail': 'Non authentifié'});
      final ds = AuthDioDataSource(_client(adapter));
      expect(await ds.currentMember(), isNull);
    });

    test('member null dans le payload → null', () async {
      final payload = Map<String, dynamic>.from(_validPayload)..['member'] = null;
      final adapter = ScriptedAdapter()
        ..on('/auth/me/', method: 'GET', status: 200, body: payload);
      final ds = AuthDioDataSource(_client(adapter));
      expect(await ds.currentMember(), isNull);
    });
  });

  group('AuthDioDataSource — changePassword', () {
    test('Succès → null', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/auth/change-password/', method: 'POST', status: 200);
      final ds = AuthDioDataSource(_client(adapter));
      final res = await ds.changePassword(
        oldPassword: 'old',
        newPassword: 'newpassword12',
      );
      expect(res, isNull);
    });

    test('400 → message d\'erreur extrait du body (pas d\'exception)',
        () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/auth/change-password/',
            method: 'POST',
            status: 400,
            body: {'detail': 'Mot de passe actuel incorrect.'});
      final ds = AuthDioDataSource(_client(adapter));
      final res = await ds.changePassword(
        oldPassword: 'wrong',
        newPassword: 'newpassword12',
      );
      expect(res, 'Mot de passe actuel incorrect.');
    });
  });
}
