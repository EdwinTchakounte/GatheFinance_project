import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/entities/savings_transaction.dart';
import 'savings_remote_datasource.dart';

/// Type de compte ciblé par cette datasource : cotisation journalière (Art.4)
/// OU épargne classique (compte libre). Les deux comptes ont des endpoints
/// distincts côté backend.
enum SavingsAccountKind { cotisation, classique }

/// Implémentation HTTP de [SavingsRemoteDataSource].
///
/// Note importante sur [deposit] : le backend n'a PAS d'endpoint "dépôt
/// direct" — un dépôt = `POST /payments/init/` (type=epargne|epargne_classique)
/// + attente du webhook Tara qui crédite réellement le solde. La méthode
/// initie donc le paiement puis renvoie le snapshot **actuel** du compte
/// (qui ne reflète pas encore le dépôt). L'UI doit poller `fetchMine()` après
/// quelques secondes pour voir le crédit.
class SavingsDioDataSource implements SavingsRemoteDataSource {
  SavingsDioDataSource(this._client, this.kind);

  final ApiClient _client;
  final SavingsAccountKind kind;

  Dio get _dio => _client.dio;

  String get _meEndpoint => switch (kind) {
        SavingsAccountKind.cotisation => '/savings/me/',
        SavingsAccountKind.classique => '/savings/classic/me/',
      };

  String get _paymentType => switch (kind) {
        SavingsAccountKind.cotisation => 'epargne',
        SavingsAccountKind.classique => 'epargne_classique',
      };

  @override
  Future<SavingsAccount> fetchMine() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(_meEndpoint);
      return _parseAccount(response.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<SavingsAccount> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
  }) async {
    try {
      final body = <String, dynamic>{
        'type': _paymentType,
        'montant': amount,
        'phone': phone,
        'network': network,
      };
      // CH-3 — Sous-canal placement (bloqué 12 mois, rapporte un intérêt
      // capitalisé à maturité). Le backend ignore is_placement pour les types
      // autres que `epargne_classique` (cf. payments/views.py:200) — on le
      // pose tout de même côté UI uniquement quand le membre l'a coché ET
      // que l'on cible bien l'épargne classique pour rester explicite.
      if (isPlacement && kind == SavingsAccountKind.classique) {
        body['is_placement'] = true;
      }
      await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: body,
      );
      // Le webhook Tara n'a pas encore crédité — on renvoie le snapshot actuel.
      return fetchMine();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

SavingsAccount _parseAccount(Map<String, dynamic> json) {
  final txList = (json['transactions_recentes'] as List<dynamic>?) ?? const [];
  final tauxRaw = json['taux_interet_applique'] ?? json['taux_interet'] ?? '0';
  return SavingsAccount(
    id: (json['id'] as num?)?.toInt() ?? 0,
    solde: _num(json['solde']),
    dateOuverture: _date(json['date_ouverture']),
    tauxInteret: _num(tauxRaw),
    transactions: txList
        .map((t) => _parseTransaction(t as Map<String, dynamic>))
        .toList(growable: false),
  );
}

SavingsTransaction _parseTransaction(Map<String, dynamic> json) {
  return SavingsTransaction(
    id: (json['id'] as num).toInt(),
    type: _type((json['type_op'] as String?) ?? 'depot'),
    montant: _num(json['montant']),
    soldeApres: _num(json['solde_apres']),
    date: _date(json['date']),
  );
}

SavingsType _type(String raw) {
  switch (raw) {
    case 'retrait':
      return SavingsType.retrait;
    case 'interet':
      return SavingsType.interet;
    case 'depot':
    default:
      return SavingsType.depot;
  }
}

num _num(dynamic value) {
  if (value is num) return value;
  if (value is String) return num.tryParse(value) ?? 0;
  return 0;
}

DateTime _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
