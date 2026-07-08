import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/network/api_client.dart';
import 'package:gathe_finance/features/avaliste/data/datasources/avaliste_dio_datasource.dart';
import 'package:gathe_finance/features/avaliste/domain/entities/avaliste_mandat.dart';

import '../../../../helpers/dio_test_adapter.dart';

ApiClient _client(ScriptedAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test.local/api/v1'))
    ..httpClientAdapter = adapter;
  return ApiClient.forTest(dio: dio);
}

Map<String, dynamic> _mandatPayload({
  int id = 42,
  String statut = 'pending',
}) {
  return {
    'id': id,
    'statut': statut,
    'statut_display': statut == 'pending' ? 'En attente' : statut,
    'responded_at': statut == 'pending' ? null : '2026-06-01T10:00:00Z',
    'refus_motif': '',
    'created_at': '2026-06-01T08:00:00Z',
    'demandeur': {
      'id': 99,
      'numero_membre': 'GF-2026-0099',
      'prenom': 'Awa',
      'nom': 'Sow',
    },
    'loan_request': {
      'id': 200,
      'montant_demande': '250000.00',
      'duree_mois': 6,
      'motif': 'Achat',
      'statut': 'en_attente_avaliste',
      'date_soumission': '2026-06-01T08:00:00Z',
    },
    'couverture': {
      'epargne_borrower': '50000.00',
      'epargne_avaliste': '300000.00',
      'ratio': '1.2',
    },
  };
}

void main() {
  group('AvalisteDioDataSource — list', () {
    test('Parse results + pendingCount', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/avaliste-mandats/',
            method: 'GET',
            status: 200,
            body: {
              'count': 2,
              'pending': 1,
              'results': [
                _mandatPayload(id: 1, statut: 'pending'),
                _mandatPayload(id: 2, statut: 'accepted'),
              ],
            },);
      final ds = AvalisteDioDataSource(_client(adapter));

      final res = await ds.list();
      expect(res.items, hasLength(2));
      expect(res.pendingCount, 1);
      expect(res.items.first.id, 1);
      expect(res.items.first.statut, AvalisteStatut.pending);
      expect(res.items.first.demandeur.fullName, 'Awa Sow');
      expect(res.items.first.loanRequest.montantDemande, 250000);
      expect(res.items.first.couverture.ratio, 1.2);
      expect(res.items[1].statut, AvalisteStatut.accepted);
    });

    test('Filtre statut → query param transmis', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/avaliste-mandats/',
            method: 'GET',
            status: 200,
            body: {'pending': 0, 'results': <Map<String, dynamic>>[]},);
      final ds = AvalisteDioDataSource(_client(adapter));

      await ds.list(statut: AvalisteStatut.accepted);
      expect(adapter.recorded.last.query['statut'], 'accepted');
    });

    test('results vide → liste vide, pendingCount 0', () async {
      final adapter = ScriptedAdapter()
        ..on('/loans/me/avaliste-mandats/',
            method: 'GET', status: 200, body: {'results': <Map<String, dynamic>>[]},);
      final ds = AvalisteDioDataSource(_client(adapter));
      final res = await ds.list();
      expect(res.items, isEmpty);
      expect(res.pendingCount, 0);
    });
  });

  group('AvalisteDioDataSource — respond', () {
    test('accept=true → multipart avec CNI + fichier', () async {
      // L5 identité . L'acceptation part en multipart : accept + numéro de CNI
      // + le fichier justificatif. On fournit un vrai fichier temporaire pour
      // que MultipartFile.fromFile puisse le lire.
      final tmp = await File(
        '${Directory.systemTemp.path}/cni_avaliste_test.png',
      ).writeAsBytes(const [1, 2, 3, 4]);
      addTearDown(() async {
        if (tmp.existsSync()) await tmp.delete();
      });
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/me/avaliste-mandats/42/respond/',
            method: 'POST',
            status: 200,
            body: _mandatPayload(id: 42, statut: 'accepted'),);
      final ds = AvalisteDioDataSource(_client(adapter));

      final r = await ds.respond(
        mandatId: 42,
        accept: true,
        cniAvaliste: 'CNI-12345',
        cniFichierPath: tmp.path,
        cniFichierName: 'cni.png',
      );
      expect(r.statut, AvalisteStatut.accepted);
      // Le body multipart contient les champs accept + cni_avaliste + le fichier.
      final sent = adapter.recorded
          .firstWhere((req) => req.path.contains('respond'));
      expect(sent.body, contains('name="accept"'));
      expect(sent.body, contains('name="cni_avaliste"'));
      expect(sent.body, contains('CNI-12345'));
      expect(sent.body, contains('name="cni_avaliste_fichier"'));
    });

    test('accept=false avec motif → motif transmis', () async {
      final adapter = ScriptedAdapter()
        ..on('/auth/csrf/', method: 'GET', status: 200)
        ..on('/loans/me/avaliste-mandats/42/respond/',
            method: 'POST',
            status: 200,
            body: _mandatPayload(id: 42, statut: 'refused'),);
      final ds = AvalisteDioDataSource(_client(adapter));

      await ds.respond(
        mandatId: 42,
        accept: false,
        motif: 'Pas la capacité',
      );
      final sent = adapter.recorded
          .firstWhere((req) => req.path.contains('respond'));
      expect(sent.body, contains('"accept":false'));
      expect(sent.body, contains('Pas la capacité'));
    });
  });
}
