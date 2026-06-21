import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/booklet/data/datasources/booklet_dio_datasource.dart';
import 'package:gathe_finance/features/booklet/domain/entities/booklet_order.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

void main() {
  test('myOrders parse statuts et dates optionnelles', () async {
    final adapter = ScriptedAdapter()
      ..on('/booklet/me/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 1,
                'statut': 'delivree',
                'statut_display': 'Délivrée',
                'date_impression': '2026-05-10T09:00:00Z',
                'date_delivrance': '2026-05-12T11:00:00Z',
                'created_at': '2026-05-01T08:00:00Z',
              },
              {
                'id': 2,
                'statut': 'en_impression',
                'statut_display': 'En impression',
                'date_impression': null,
                'date_delivrance': null,
                'created_at': '2026-06-01T08:00:00Z',
              },
              {
                'id': 3,
                'statut': 'payee',
                'statut_display': 'Payée',
                'date_impression': null,
                'date_delivrance': null,
                'created_at': '2026-06-02T08:00:00Z',
              },
            ],
          },);
    final ds = BookletDioDataSource(_client(adapter));
    final orders = await ds.myOrders();
    expect(orders, hasLength(3));
    expect(orders[0].statut, BookletStatus.delivree);
    expect(orders[0].dateDelivrance, isNotNull);
    expect(orders[1].statut, BookletStatus.enImpression);
    expect(orders[1].dateImpression, isNull);
    expect(orders[2].statut, BookletStatus.payee);
  });

  test('order POST /payments/init/ type=frais_carnet + refetch', () async {
    final adapter = ScriptedAdapter()
      ..on('/auth/csrf/', method: 'GET', status: 200)
      ..on('/payments/init/',
          method: 'POST',
          status: 200,
          body: {'payment': {'id': 1}},)
      ..on('/booklet/me/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 42,
                'statut': 'payee',
                'statut_display': 'Payée',
                'date_impression': null,
                'date_delivrance': null,
                'created_at': '2026-06-04T10:00:00Z',
              },
            ],
          },);
    final ds = BookletDioDataSource(_client(adapter));
    final order = await ds.order(phone: '+237699112233', network: 'MTN');
    expect(order.id, 42);
    expect(order.statut, BookletStatus.payee);
    final init = adapter.recorded
        .firstWhere((r) => r.path.contains('/payments/init/'));
    expect(init.body, contains('"type":"frais_carnet"'));
    expect(init.body, contains('"network":"MTN"'));
  });

  test('order avec backend vide → placeholder payée id=0', () async {
    final adapter = ScriptedAdapter()
      ..on('/auth/csrf/', method: 'GET', status: 200)
      ..on('/payments/init/',
          method: 'POST',
          status: 200,
          body: {'payment': {'id': 1}},)
      ..on('/booklet/me/',
          method: 'GET',
          status: 200,
          body: {'results': <Map<String, dynamic>>[]},);
    final ds = BookletDioDataSource(_client(adapter));
    final order = await ds.order(phone: '+237', network: 'WAVE');
    expect(order.id, 0);
    expect(order.statut, BookletStatus.payee);
  });
}
