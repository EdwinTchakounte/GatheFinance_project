import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../di/providers.dart';

/// Tous les taux métier courants, lus depuis `/payments/rates/`, indexés par
/// code (`LOAN_INTEREST`, `SAVINGS_INTEREST_MONTHLY`, `TRANSACTION_FEE`, …).
/// Valeurs = ratios (ex. 0.10 = 10 %).
///
/// Best-effort : renvoie une map vide en cas d'absence/erreur — le reçu affiche
/// alors simplement les lignes disponibles, jamais de crash.
final paymentRatesProvider = FutureProvider<Map<String, double>>((ref) async {
  try {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>('/payments/rates/');
    final data = res.data ?? const {};
    final out = <String, double>{};
    data.forEach((code, payload) {
      if (payload is Map && payload['valeur'] != null) {
        final v = double.tryParse(payload['valeur'].toString());
        if (v != null) out[code] = v;
      }
    });
    return out;
  } catch (_) {
    return const {};
  }
});
