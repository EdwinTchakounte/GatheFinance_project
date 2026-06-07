import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/savings/data/datasources/savings_dio_datasource.dart';
import 'package:gathe_finance/features/savings/domain/entities/savings_transaction.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

const _accountPayload = {
  'id': 12,
  'solde': '50000.00',
  'date_ouverture': '2026-01-15',
  'taux_interet_applique': '0.01',
  'transactions_recentes': [
    {
      'id': 1,
      'type_op': 'depot',
      'type_display': 'Dépôt',
      'montant': '1000.00',
      'solde_apres': '50000.00',
      'date': '2026-06-01T10:00:00Z',
    },
    {
      'id': 2,
      'type_op': 'interet',
      'type_display': 'Intérêt',
      'montant': '490.00',
      'solde_apres': '49000.00',
      'date': '2026-05-31T23:00:00Z',
    },
  ],
};

void main() {
  group('SavingsDioDataSource — cotisation', () {
    test('fetchMine parse solde + transactions', () async {
      final adapter = ScriptedAdapter()
        ..on('/savings/me/',
            method: 'GET', status: 200, body: _accountPayload);
      final ds = SavingsDioDataSource(
        _client(adapter),
        SavingsAccountKind.cotisation,
      );

      final acc = await ds.fetchMine();
      expect(acc.id, 12);
      expect(acc.solde, 50000);
      expect(acc.tauxInteret, 0.01);
      expect(acc.transactions, hasLength(2));
      expect(acc.transactions.first.type, SavingsType.depot);
      expect(acc.transactions[1].type, SavingsType.interet);
    });

    test('deposit POST /payments/init/ type=epargne + refetch', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/payments/init/',
            method: 'POST',
            status: 200,
            body: {'payment': {'id': 1}})
        ..on('/savings/me/',
            method: 'GET', status: 200, body: _accountPayload);
      final ds = SavingsDioDataSource(
        _client(adapter),
        SavingsAccountKind.cotisation,
      );

      await ds.deposit(amount: 1000, phone: '+237699112233', network: 'MTN');
      final init = adapter.recorded
          .firstWhere((r) => r.path.contains('/payments/init/'));
      expect(init.body, contains('"type":"epargne"'));
      expect(init.body, contains('"montant":1000'));
      expect(init.body, contains('"network":"MTN"'));
    });
  });

  group('SavingsDioDataSource — classique', () {
    test('fetchMine appelle /savings/classic/me/', () async {
      final adapter = ScriptedAdapter()
        ..on('/savings/classic/me/',
            method: 'GET', status: 200, body: _accountPayload);
      final ds = SavingsDioDataSource(
        _client(adapter),
        SavingsAccountKind.classique,
      );
      final acc = await ds.fetchMine();
      expect(acc.solde, 50000);
    });

    test('deposit POST type=epargne_classique', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/payments/init/',
            method: 'POST',
            status: 200,
            body: {'payment': {'id': 1}})
        ..on('/savings/classic/me/',
            method: 'GET', status: 200, body: _accountPayload);
      final ds = SavingsDioDataSource(
        _client(adapter),
        SavingsAccountKind.classique,
      );
      await ds.deposit(amount: 5000, phone: '+237699112233', network: 'ORANGE');
      final init = adapter.recorded
          .firstWhere((r) => r.path.contains('/payments/init/'));
      expect(init.body, contains('"type":"epargne_classique"'));
    });
  });
}
