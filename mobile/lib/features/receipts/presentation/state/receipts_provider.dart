import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/payment_receipt.dart';

/// Historique complet des versements du membre (`GET /payments/me/`), tous
/// types confondus (épargne, remboursement, frais…). Alimente la page « Mes
/// reçus » : chaque versement peut générer une mini-facture téléchargeable.
final receiptsProvider = FutureProvider<List<PaymentReceipt>>((ref) async {
  final dio = ref.read(apiClientProvider).dio;
  try {
    final res = await dio.get<Map<String, dynamic>>('/payments/me/');
    final results = (res.data?['results'] as List<dynamic>?) ?? const [];
    final list = results
        .map((r) => PaymentReceipt.fromJson(r as Map<String, dynamic>))
        .toList(growable: false);
    // Tri antéchronologique (plus récent d'abord).
    final sorted = [...list]..sort((a, b) => b.date.compareTo(a.date));
    return sorted;
  } on DioException catch (e) {
    throw mapDioError(e);
  }
});
