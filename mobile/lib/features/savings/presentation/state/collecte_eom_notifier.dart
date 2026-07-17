import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';

/// Choix de fin de mois de la collecte : `'cash'` (retrait) ou `'epargne'`
/// (bascule vers l'épargne classique). Piloté par le membre, respecté par le
/// cron mensuel côté backend.
class CollecteEomNotifier extends AsyncNotifier<String> {
  Future<String> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>(
      '/savings/me/end-of-month-preference/',
    );
    return (res.data?['preference'] as String?) ?? 'cash';
  }

  @override
  Future<String> build() => _fetch();

  Future<void> setPreference(String preference) async {
    // Optimiste : bascule l'UI tout de suite, puis persiste.
    state = AsyncData(preference);
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>(
      '/savings/me/end-of-month-preference/',
      data: {'preference': preference},
    );
  }
}

final collecteEomProvider =
    AsyncNotifierProvider<CollecteEomNotifier, String>(CollecteEomNotifier.new);
