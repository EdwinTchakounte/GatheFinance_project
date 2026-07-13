import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../../../core/services/tara_checkout_launcher.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/entities/savings_transaction.dart';
import '../../domain/entities/withdrawal_request.dart';
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
    int nbJoursCouverts = 1,
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
      // LOT 6 — Multi-jours pré-payé : valide UNIQUEMENT pour la cotisation
      // journalière (type=`epargne`). Le backend rejette `nb_jours_couverts>1`
      // sur les autres types. On ne propage qu'à partir de 2 jours pour
      // garder le wire compact.
      if (nbJoursCouverts > 1 && kind == SavingsAccountKind.cotisation) {
        body['nb_jours_couverts'] = nbJoursCouverts;
      }
      final response = await _dio.post<Map<String, dynamic>>(
        '/payments/init/',
        data: body,
      );
      // Stocke la reponse Tara (vendor / status / message) pour que le
      // sheet success step l'affiche au membre.
      LastTaraResponse.update(response.data);
      // Tara héberge la page de paiement : on ouvre paymentUrl dans le
      // navigateur externe pour que le membre confirme avec son PIN MoMo.
      // Le webhook Tara créditera ensuite le solde côté backend.
      await TaraCheckoutLauncher.launchFromInitResponse(response.data);
      // Le webhook Tara n'a pas encore crédité — on renvoie le snapshot actuel.
      return fetchMine();
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<WithdrawalRequest> requestWithdrawal({
    required num amount,
    required String motif,
    required WithdrawalChannel channel,
    String recipientPhone = '',
    MomoNetwork? network,
    WithdrawalSource source = WithdrawalSource.collecte,
  }) async {
    try {
      final body = <String, dynamic>{
        'montant': amount,
        'motif': motif,
        'source': _sourceToApi(source),
        'mode_paiement': _channelToApi(channel),
      };
      if (channel == WithdrawalChannel.momo) {
        body['recipient_phone'] = recipientPhone;
        body['network'] = _networkToApi(network!);
      }
      final response = await _dio.post<Map<String, dynamic>>(
        '/savings/withdrawal/',
        data: body,
      );
      return _parseWithdrawal(response.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<List<WithdrawalRequest>> listMyWithdrawals() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/savings/withdrawals/me/',
      );
      final results = (response.data?['results'] as List<dynamic>?) ?? const [];
      return results
          .map((e) => _parseWithdrawal(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

String _channelToApi(WithdrawalChannel c) => switch (c) {
      WithdrawalChannel.momo => 'momo',
      WithdrawalChannel.presentiel => 'presentiel',
    };

String _sourceToApi(WithdrawalSource s) => switch (s) {
      WithdrawalSource.collecte => 'collecte',
      WithdrawalSource.classiqueLibre => 'classique_libre',
    };

String _networkToApi(MomoNetwork n) => switch (n) {
      MomoNetwork.mtn => 'MTN',
      MomoNetwork.orange => 'ORANGE',
      MomoNetwork.wave => 'WAVE',
      MomoNetwork.airtel => 'AIRTEL',
    };

WithdrawalChannel _channelFromApi(String raw) => switch (raw) {
      'momo' => WithdrawalChannel.momo,
      _ => WithdrawalChannel.presentiel,
    };

MomoNetwork? _networkFromApi(String? raw) => switch (raw) {
      'MTN' => MomoNetwork.mtn,
      'ORANGE' => MomoNetwork.orange,
      'WAVE' => MomoNetwork.wave,
      'AIRTEL' => MomoNetwork.airtel,
      _ => null,
    };

WithdrawalStatus _statusFromApi(String? raw) => switch (raw) {
      'approuvee' => WithdrawalStatus.approuvee,
      'en_payout' => WithdrawalStatus.enPayout,
      'completee' => WithdrawalStatus.completee,
      'payout_failed' => WithdrawalStatus.payoutFailed,
      'rejetee' => WithdrawalStatus.rejetee,
      _ => WithdrawalStatus.enAttente,
    };

WithdrawalRequest _parseWithdrawal(Map<String, dynamic> json) {
  return WithdrawalRequest(
    id: (json['id'] as num?)?.toInt() ?? 0,
    montant: _num(json['montant']),
    motif: (json['motif'] as String?) ?? '',
    statut: _statusFromApi(json['statut'] as String?),
    statutDisplay: (json['statut_display'] as String?) ?? '',
    modePaiement: _channelFromApi((json['mode_paiement'] as String?) ?? ''),
    modePaiementDisplay: (json['mode_paiement_display'] as String?) ?? '',
    recipientPhoneMasked: (json['recipient_phone_masked'] as String?) ?? '',
    network: _networkFromApi(json['network'] as String?),
    motifRejet: (json['motif_rejet'] as String?) ?? '',
    dateDemande: _date(json['date_demande']),
    dateDecision: json['date_decision'] != null
        ? _date(json['date_decision'])
        : null,
    handedOverAt: json['handed_over_at'] != null
        ? _date(json['handed_over_at'])
        : null,
  );
}

SavingsAccount _parseAccount(Map<String, dynamic> json) {
  final txList = (json['transactions_recentes'] as List<dynamic>?) ?? const [];
  final tauxRaw = json['taux_interet_applique'] ?? json['taux_interet'] ?? '0';
  return SavingsAccount(
    id: (json['id'] as num?)?.toInt() ?? 0,
    solde: _num(json['solde']),
    // Épargne classique (refonte garantie 2026) : ces clés sont absentes du
    // snapshot collecte → on ne les matérialise que si présentes pour laisser
    // [soldeRetirable] retomber sur le solde complet côté collecte.
    soldeLibre: json.containsKey('solde_libre') ? _num(json['solde_libre']) : null,
    soldePlacementActif: json.containsKey('solde_placement_actif')
        ? _num(json['solde_placement_actif'])
        : null,
    soldeDisponibleRetrait: json.containsKey('solde_disponible_retrait')
        ? _num(json['solde_disponible_retrait'])
        : null,
    montantGeleCredit: json.containsKey('montant_gele_credit')
        ? _num(json['montant_gele_credit'])
        : null,
    // Fenêtre placement par membre (épargne classique) : présent uniquement sur
    // le snapshot classique → null côté collecte (l'UI le traite comme ouvert).
    placementOpen: json['placement_open'] as bool?,
    placementEligibilityMonths:
        (json['placement_eligibility_months'] as num?)?.toInt(),
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
