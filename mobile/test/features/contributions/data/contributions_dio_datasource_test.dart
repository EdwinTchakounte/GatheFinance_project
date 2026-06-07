import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/contributions/data/contributions_dio_datasource.dart';
import 'package:gathe_finance/features/contributions/domain/entities/contribution.dart';

import '../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

void main() {
  test('Filtre uniquement les frais — exclut epargne/remboursement', () async {
    final adapter = ScriptedAdapter()
      ..on('/payments/me/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 1,
                'type': 'frais_adhesion',
                'type_display': 'Adhésion',
                'montant': '10000.00',
                'source': 'mobile_money',
                'statut': 'valide',
                'statut_display': 'Validé',
                'reference_externe': 'ref-1',
                'date_versement': '2026-05-01T10:00:00Z',
                'date_validation': '2026-05-01T10:00:05Z',
                'created_at': '2026-05-01T10:00:00Z',
                'motif_rejet': '',
                'provider_code': 'tara',
              },
              {
                // doit être filtré
                'id': 2,
                'type': 'epargne',
                'type_display': 'Épargne',
                'montant': '1000.00',
                'source': 'mobile_money',
                'statut': 'valide',
                'reference_externe': 'ref-2',
                'date_versement': '2026-05-02T10:00:00Z',
                'created_at': '2026-05-02T10:00:00Z',
                'motif_rejet': '',
                'provider_code': 'tara',
              },
              {
                'id': 3,
                'type': 'frais_carnet',
                'type_display': 'Carnet',
                'montant': '1000.00',
                'source': 'mobile_money',
                'statut': 'en_attente',
                'reference_externe': 'ref-3',
                'date_versement': '2026-05-03T10:00:00Z',
                'created_at': '2026-05-03T10:00:00Z',
                'motif_rejet': '',
                'provider_code': 'tara',
              },
              {
                // doit être filtré
                'id': 4,
                'type': 'remboursement',
                'type_display': 'Remboursement',
                'montant': '5000.00',
                'source': 'mobile_money',
                'statut': 'valide',
                'reference_externe': 'ref-4',
                'date_versement': '2026-05-04T10:00:00Z',
                'created_at': '2026-05-04T10:00:00Z',
                'motif_rejet': '',
                'provider_code': 'tara',
              },
            ],
          });
    final ds = ContributionsDioDataSource(_client(adapter));
    final res = await ds.fetchMine();
    expect(res, hasLength(2)); // 2 frais retenus, epargne + remboursement exclus
    expect(res[0].type, ContributionType.fraisAdhesion);
    expect(res[0].statut, ContributionStatus.valide);
    expect(res[1].type, ContributionType.fraisCarnet);
    expect(res[1].statut, ContributionStatus.enAttente);
  });

  test('statut rejete → echec', () async {
    final adapter = ScriptedAdapter()
      ..on('/payments/me/',
          method: 'GET',
          status: 200,
          body: {
            'results': [
              {
                'id': 1,
                'type': 'frais_inscription',
                'montant': '2000',
                'source': 'mobile_money',
                'statut': 'rejete',
                'reference_externe': 'ref-x',
                'date_versement': '2026-05-01T10:00:00Z',
                'created_at': '2026-05-01T10:00:00Z',
              },
            ],
          });
    final ds = ContributionsDioDataSource(_client(adapter));
    final res = await ds.fetchMine();
    expect(res.first.statut, ContributionStatus.echec);
  });
}
