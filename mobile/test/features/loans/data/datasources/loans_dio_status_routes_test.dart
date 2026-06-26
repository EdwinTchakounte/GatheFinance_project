/// Tests des nouveaux statuts fins LoanRequest + parsing du champ `route`
/// (BRC / Avaliste / Campagne).
///
/// Couvre les 11 statuts backend + 3 voies pour garantir que le mobile ne
/// retombe plus dans le piege de l'agregation par defaut (rejetee,
/// enAttente). Verifie aussi que la nouvelle propriete
/// LoanRequestEntity.route est correctement extraite des cles
/// alternatives utilisees par le serializer ('route' ou
/// 'eligibility_route').
library;

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/loans/data/datasources/loans_dio_datasource.dart';
import 'package:gathe_finance/features/loans/domain/entities/loan_request.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

Map<String, dynamic> _request({
  required String statut,
  Map<String, dynamic>? extra,
}) {
  return {
    'id': 1,
    'montant_demande': '150000',
    'duree_mois': 6,
    'motif': 'Achat marchandise',
    'statut': statut,
    'date_soumission': '2026-06-01T08:00:00Z',
    if (extra != null) ...extra,
  };
}

void main() {
  group('LoanRequestStatus . mapping fin des 11 statuts backend', () {
    final cases = <String, LoanRequestStatus>{
      'en_attente': LoanRequestStatus.enAttente,
      'en_instruction': LoanRequestStatus.enInstruction,
      'en_attente_acceptation_membre':
          LoanRequestStatus.enAttenteAcceptationMembre,
      'approuvee_provisoire': LoanRequestStatus.approuveeProvisoire,
      'approuvee': LoanRequestStatus.approuvee,
      'rejetee': LoanRequestStatus.rejetee,
      'en_attente_avaliste': LoanRequestStatus.enAttenteAvaliste,
      'rejetee_avaliste': LoanRequestStatus.rejeteeAvaliste,
      'en_validation_campagne': LoanRequestStatus.enValidationCampagne,
      'rejetee_campagne': LoanRequestStatus.rejeteeCampagne,
      'en_attente_funding': LoanRequestStatus.enAttenteFunding,
    };

    for (final entry in cases.entries) {
      test('backend statut "${entry.key}" -> ${entry.value}', () async {
        final adapter = ScriptedAdapter()
          ..on(
            '/loans/me/requests/',
            method: 'GET',
            status: 200,
            body: [_request(statut: entry.key)],
          );
        final ds = LoansDioDataSource(_client(adapter));
        final list = await ds.myRequests();
        expect(list, hasLength(1));
        expect(list.first.statut, entry.value);
      });
    }

    test('statut inconnu retombe sur enAttente (defensive default)',
        () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [_request(statut: 'truc_qui_existe_pas')],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.statut, LoanRequestStatus.enAttente);
    });
  });

  group('LoanRoute . parsing route 3 voies', () {
    test('route="senior_brc" -> LoanRoute.seniorBrc', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'approuvee',
              extra: {'route': 'senior_brc'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.route, LoanRoute.seniorBrc);
    });

    test('route="brc" (alias court) -> LoanRoute.seniorBrc', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [_request(statut: 'approuvee', extra: {'route': 'brc'})],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.route, LoanRoute.seniorBrc);
    });

    test('eligibility_route="avaliste" -> LoanRoute.avaliste', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'en_attente_avaliste',
              extra: {'eligibility_route': 'avaliste'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.statut, LoanRequestStatus.enAttenteAvaliste);
      expect(list.first.route, LoanRoute.avaliste);
    });

    test('route="campagne" -> LoanRoute.campagne', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'en_validation_campagne',
              extra: {'route': 'campagne'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.route, LoanRoute.campagne);
    });

    test('aucune cle route -> route null (legacy ou non encore decide)',
        () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [_request(statut: 'en_attente')],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.route, isNull);
    });

    test('route="valeur_inconnue" -> route null (defensive)', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(statut: 'en_attente', extra: {'route': 'plouf'}),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final list = await ds.myRequests();
      expect(list.first.route, isNull);
    });
  });

  group('Coherence statut + route (scenarios end-to-end)', () {
    test('Voie BRC -> approuvee + seniorBrc', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'approuvee',
              extra: {'route': 'senior_brc'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final r = (await ds.myRequests()).first;
      expect(r.statut, LoanRequestStatus.approuvee);
      expect(r.route, LoanRoute.seniorBrc);
    });

    test('Voie Avaliste . attente du consentement', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'en_attente_avaliste',
              extra: {'route': 'avaliste'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final r = (await ds.myRequests()).first;
      expect(r.statut, LoanRequestStatus.enAttenteAvaliste);
      expect(r.route, LoanRoute.avaliste);
    });

    test('Voie Avaliste . refus terminal', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'rejetee_avaliste',
              extra: {
                'route': 'avaliste',
                'motif_rejet': 'L\'avaliste a refuse.',
              },
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final r = (await ds.myRequests()).first;
      expect(r.statut, LoanRequestStatus.rejeteeAvaliste);
      expect(r.route, LoanRoute.avaliste);
      expect(r.motifRejet, contains('refuse'));
    });

    test('Voie Campagne . refus profil non eligible', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'rejetee_campagne',
              extra: {
                'route': 'campagne',
                'motif_rejet': 'Profil non match campagne.',
              },
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final r = (await ds.myRequests()).first;
      expect(r.statut, LoanRequestStatus.rejeteeCampagne);
      expect(r.route, LoanRoute.campagne);
    });

    test('Voie BRC . en attente du financement preteurs (24h)', () async {
      final adapter = ScriptedAdapter()
        ..on(
          '/loans/me/requests/',
          method: 'GET',
          status: 200,
          body: [
            _request(
              statut: 'en_attente_funding',
              extra: {'route': 'senior_brc'},
            ),
          ],
        );
      final ds = LoansDioDataSource(_client(adapter));
      final r = (await ds.myRequests()).first;
      expect(r.statut, LoanRequestStatus.enAttenteFunding);
      expect(r.route, LoanRoute.seniorBrc);
    });
  });
}
