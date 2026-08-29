import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../domain/entities/booklet_order.dart';
import 'booklet_remote_datasource.dart';

/// Implémentation HTTP de [BookletRemoteDataSource].
///
///   - GET  /booklet/me/         → liste paginée (clé `results`)
///   - POST /payments/init/ +    → commander un carnet = payer `frais_carnet`,
///     fetch /booklet/me/         le BookletOrder est créé côté webhook
///                                quand le paiement est validé.
class BookletDioDataSource implements BookletRemoteDataSource {
  BookletDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<List<BookletOrder>> myOrders() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/booklet/me/');
      final results = (res.data?['results'] as List<dynamic>?) ?? const [];
      return results
          .map((r) => _parseOrder(r as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<BookletOrder> order({
    required String phone,
    required String network,
    int? montant,
  }) async {
    try {
      // Le tarif `frais_carnet` fait autorité côté backend (FeeType) : le
      // montant envoyé ici n'est qu'un défaut, le backend l'écrase. Le webhook
      // Tara crée le BookletOrder à la validation du paiement.
      final response = await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: {
          'type': 'frais_carnet',
          'montant': montant ?? 1000,
          'phone': phone,
          'network': network,
        },
      );
      // Stocke vendor/status Tara pour le success step.
      LastTaraResponse.update(response.data);
      // Ouvre la page de paiement Tara pour que le membre confirme avec PIN MoMo.
      await TaraCheckoutLauncher.launchFromInitResponse(response.data);
      final orders = await myOrders();
      if (orders.isEmpty) {
        // Le paiement est en attente côté Tara — on renvoie un placeholder
        // "payée" en attendant. L'UI rafraîchit via myOrders() après quelques
        // secondes.
        return BookletOrder(
          id: 0,
          statut: BookletStatus.payee,
          dateCommande: DateTime.now(),
          montant: 0,
        );
      }
      return orders.first;
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

BookletOrder _parseOrder(Map<String, dynamic> json) {
  return BookletOrder(
    id: (json['id'] as num).toInt(),
    statut: _status((json['statut'] as String?) ?? 'payee'),
    typeDisplay: (json['type_display'] as String?) ?? '',
    dateCommande: _date(json['created_at']),
    montant: 0, // non exposé par le serializer (à ajouter si besoin)
    dateImpression: json['date_impression'] != null
        ? _date(json['date_impression'])
        : null,
    dateDelivrance: json['date_delivrance'] != null
        ? _date(json['date_delivrance'])
        : null,
  );
}

BookletStatus _status(String raw) {
  switch (raw) {
    case 'en_impression':
      return BookletStatus.enImpression;
    case 'delivree':
      return BookletStatus.delivree;
    case 'payee':
    default:
      return BookletStatus.payee;
  }
}

DateTime _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
