// D5 . Provider pour /api/v1/members/me/renewal-status/. Banniere Home affichee
// si needs_renewal=true ou statut=suspendu. Best-effort : la home affiche le
// reste meme si l'appel echoue.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';


class RenewalStatus {
  RenewalStatus({
    required this.needsRenewal,
    required this.inWarningWindow,
    required this.daysUntilExpiry,
    required this.statut,
    required this.carnetFeeXaf,
    required this.gracedays,
  });

  final bool needsRenewal;
  final bool inWarningWindow;
  final int? daysUntilExpiry;
  final String statut;
  final String? carnetFeeXaf;
  final int gracedays;

  factory RenewalStatus.fromJson(Map<String, dynamic> j) {
    return RenewalStatus(
      needsRenewal: j['needs_renewal'] == true,
      inWarningWindow: j['in_warning_window'] == true,
      daysUntilExpiry: j['days_until_expiry'] as int?,
      statut: (j['statut'] as String?) ?? '',
      carnetFeeXaf: j['carnet_fee_xaf'] as String?,
      gracedays: (j['grace_days'] as int?) ?? 30,
    );
  }

  bool get isSuspended => statut == 'suspendu';
  // Banniere visible si dans la fenetre [J-30..J+grace] OU suspendu.
  bool get shouldShowBanner => needsRenewal || isSuspended;
}


final renewalStatusProvider = FutureProvider.autoDispose<RenewalStatus?>(
  (ref) async {
    final dio = ref.watch(apiClientProvider).dio;
    try {
      final res = await dio.get<Map<String, dynamic>>(
        '/members/me/renewal-status/',
      );
      final data = res.data;
      if (data == null) return null;
      return RenewalStatus.fromJson(data);
    } on DioException {
      // Best-effort . on n'affiche pas la banniere si l'appel echoue.
      return null;
    }
  },
);
