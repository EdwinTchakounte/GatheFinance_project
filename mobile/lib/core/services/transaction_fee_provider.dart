import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../di/providers.dart';

/// Taux de frais de transaction (%) courant, lu depuis `/payments/rates/`
/// (clé `TRANSACTION_FEE`). Ratio (ex. 0.02 = 2 %).
///
/// Best-effort : renvoie 0.0 si non configuré, absent ou en cas d'erreur —
/// n'empêche jamais l'affichage d'un versement.
final transactionFeeRateProvider = FutureProvider<double>((ref) async {
  try {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>('/payments/rates/');
    final tf = res.data?['TRANSACTION_FEE'];
    if (tf is Map && tf['valeur'] != null) {
      return double.tryParse(tf['valeur'].toString()) ?? 0.0;
    }
    return 0.0;
  } catch (_) {
    return 0.0;
  }
});
