import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/notifications/data/datasources/notifications_dio_datasource.dart';
import 'package:gathe_finance/features/notifications/domain/entities/app_notification.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

void main() {
  test('list parse results + map kind par préfixe', () async {
    final adapter = ScriptedAdapter()
      ..on('/notifications/',
          method: 'GET',
          status: 200,
          body: {
            'unread_count': 2,
            'results': [
              {
                'id': 1,
                'type': 'payment.confirmed',
                'message': 'Dépôt validé.',
                'lien': '',
                'lue': false,
                'created_at': '2026-06-01T10:00:00Z',
              },
              {
                'id': 2,
                'type': 'loan.disbursed',
                'message': 'Crédit décaissé.',
                'lien': '',
                'lue': true,
                'created_at': '2026-05-31T08:00:00Z',
              },
              {
                'id': 3,
                'type': 'savings.interest_added',
                'message': 'Intérêt mensuel crédité.',
                'lien': '',
                'lue': false,
                'created_at': '2026-05-30T08:00:00Z',
              },
              {
                'id': 4,
                'type': 'withdrawal.completed',
                'message': 'Retrait reçu.',
                'lien': '',
                'lue': false,
                'created_at': '2026-05-29T08:00:00Z',
              },
              {
                'id': 5,
                'type': 'system.welcome',
                'message': 'Bienvenue.',
                'lien': '',
                'lue': false,
                'created_at': '2026-05-28T08:00:00Z',
              },
            ],
          },);
    final ds = NotificationsDioDataSource(_client(adapter));
    final list = await ds.list();
    expect(list, hasLength(5));
    expect(list[0].kind, NotifKind.payment);
    expect(list[1].kind, NotifKind.loan);
    expect(list[2].kind, NotifKind.savings);
    expect(list[3].kind, NotifKind.savings); // withdrawal → savings
    expect(list[4].kind, NotifKind.system);
    expect(list[1].read, isTrue);
  });

  test('markRead POST /notifications/{id}/read/', () async {
    final adapter = ScriptedAdapter()
      ..on('/auth/csrf/', method: 'GET', status: 200)
      ..on('/notifications/42/read/', method: 'POST', status: 200);
    final ds = NotificationsDioDataSource(_client(adapter));
    await ds.markRead(42);
    final post = adapter.recorded
        .firstWhere((r) => r.path.contains('/notifications/42/read/'));
    expect(post.method, 'POST');
  });

  test('markAllRead POST /notifications/read-all/', () async {
    final adapter = ScriptedAdapter()
      ..on('/auth/csrf/', method: 'GET', status: 200)
      ..on('/notifications/read-all/', method: 'POST', status: 200);
    final ds = NotificationsDioDataSource(_client(adapter));
    await ds.markAllRead();
    final post = adapter.recorded
        .firstWhere((r) => r.path.contains('/notifications/read-all/'));
    expect(post.method, 'POST');
  });

  test(
      'type=annonce → title extrait du préfixe "TITRE\\n\\nCORPS"',
      () async {
    final adapter = ScriptedAdapter()
      ..on('/notifications/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 7,
                'type': 'annonce',
                'message':
                    'Fermeture exceptionnelle\n\nLa coopérative sera fermée vendredi 12 juin pour formation.',
                'lien': '',
                'lue': false,
                'created_at': '2026-06-07T10:00:00Z',
              },
              // Cas dégradé : pas de double-saut, on bascule sur "Annonce".
              {
                'id': 8,
                'type': 'annonce',
                'message': 'Message sans titre détectable',
                'lien': '',
                'lue': false,
                'created_at': '2026-06-07T10:01:00Z',
              },
            ],
          },);
    final ds = NotificationsDioDataSource(_client(adapter));
    final list = await ds.list();
    expect(list[0].title, 'Fermeture exceptionnelle');
    expect(
      list[0].body,
      'La coopérative sera fermée vendredi 12 juin pour formation.',
    );
    expect(list[0].kind, NotifKind.announcement);
    expect(list[1].title, 'Annonce');
    expect(list[1].body, 'Message sans titre détectable');
    expect(list[1].kind, NotifKind.announcement);
  });

  test('Title dérivé du type (type.subtype → "Type Subtype")', () async {
    final adapter = ScriptedAdapter()
      ..on('/notifications/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 1,
                'type': 'payment.confirmed',
                'message': 'msg',
                'lue': false,
                'created_at': '2026-06-01T10:00:00Z',
              },
            ],
          },);
    final ds = NotificationsDioDataSource(_client(adapter));
    final list = await ds.list();
    expect(list.first.title, 'Payment Confirmed');
  });
}
