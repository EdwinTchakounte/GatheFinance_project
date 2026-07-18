import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';

/// Choix de fin de mois de la collecte, avec sa destination Mobile Money
/// éventuelle. Piloté par le membre, respecté par le cron mensuel côté backend.
class CollecteEomPref {
  const CollecteEomPref({
    required this.preference,
    this.payoutPhone = '',
    this.payoutNetwork = '',
  });

  /// `'cash'` (retrait agence), `'mobile_money'` (versement) ou `'epargne'`.
  final String preference;
  final String payoutPhone;
  final String payoutNetwork;

  CollecteEomPref copyWith({
    String? preference,
    String? payoutPhone,
    String? payoutNetwork,
  }) {
    return CollecteEomPref(
      preference: preference ?? this.preference,
      payoutPhone: payoutPhone ?? this.payoutPhone,
      payoutNetwork: payoutNetwork ?? this.payoutNetwork,
    );
  }
}

class CollecteEomNotifier extends AsyncNotifier<CollecteEomPref> {
  Future<CollecteEomPref> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>(
      '/savings/me/end-of-month-preference/',
    );
    final data = res.data ?? const <String, dynamic>{};
    return CollecteEomPref(
      preference: (data['preference'] as String?) ?? 'cash',
      payoutPhone: (data['payout_phone'] as String?) ?? '',
      payoutNetwork: (data['payout_network'] as String?) ?? '',
    );
  }

  @override
  Future<CollecteEomPref> build() => _fetch();

  /// Enregistre le choix. Pour `mobile_money`, [phone] est requis ; [network]
  /// optionnel (MTN / ORANGE…). Optimiste : bascule l'UI puis persiste ;
  /// recharge la vérité serveur en cas d'échec.
  Future<void> setPreference(
    String preference, {
    String phone = '',
    String network = '',
  }) async {
    final previous = state.valueOrNull;
    state = AsyncData(
      CollecteEomPref(
        preference: preference,
        payoutPhone: phone,
        payoutNetwork: network,
      ),
    );
    final dio = ref.read(apiClientProvider).dio;
    final payload = <String, dynamic>{'preference': preference};
    if (preference == 'mobile_money') {
      payload['payout_phone'] = phone;
      payload['payout_network'] = network;
    }
    try {
      await dio.post<Map<String, dynamic>>(
        '/savings/me/end-of-month-preference/',
        data: payload,
      );
    } catch (_) {
      // Restaure l'état précédent (destination requise refusée, réseau, etc.).
      if (previous != null) {
        state = AsyncData(previous);
      }
      rethrow;
    }
  }
}

final collecteEomProvider =
    AsyncNotifierProvider<CollecteEomNotifier, CollecteEomPref>(
  CollecteEomNotifier.new,
);
