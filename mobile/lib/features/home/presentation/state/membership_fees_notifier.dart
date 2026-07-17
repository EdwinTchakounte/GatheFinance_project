import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';

/// Statut des frais membre (adhésion / inscription) : montants + solvabilité
/// du compte + statut du membre. Alimente le carrousel de paiement in-app.
class MembershipFeesState {
  const MembershipFeesState({
    required this.statut,
    required this.available,
    required this.adhesionAmount,
    required this.adhesionSolvable,
    required this.inscriptionAmount,
    required this.inscriptionSolvable,
  });

  final String statut;
  final num available;
  final num adhesionAmount;
  final bool adhesionSolvable;
  final num inscriptionAmount;
  final bool inscriptionSolvable;

  bool get isActive => statut == 'actif';

  factory MembershipFeesState.fromJson(Map<String, dynamic> j) {
    final fees = (j['fees'] as Map<String, dynamic>? ?? const {});
    final adh = (fees['ADHESION'] as Map<String, dynamic>? ?? const {});
    final ins = (fees['INSCRIPTION'] as Map<String, dynamic>? ?? const {});
    num p(Object? v) => num.tryParse('${v ?? 0}') ?? 0;
    return MembershipFeesState(
      statut: j['statut'] as String? ?? '',
      available: p(j['available']),
      adhesionAmount: p(adh['montant']),
      adhesionSolvable: adh['solvable'] == true,
      inscriptionAmount: p(ins['montant']),
      inscriptionSolvable: ins['solvable'] == true,
    );
  }
}

class MembershipFeesNotifier extends AsyncNotifier<MembershipFeesState> {
  Future<MembershipFeesState> _fetch() async {
    final dio = ref.read(apiClientProvider).dio;
    final res = await dio.get<Map<String, dynamic>>('/me/fees/');
    return MembershipFeesState.fromJson(res.data ?? const {});
  }

  @override
  Future<MembershipFeesState> build() => _fetch();

  Future<void> refresh() async {
    state = await AsyncValue.guard(_fetch);
  }

  /// Règle un frais depuis le compte (transfert interne, synchrone).
  Future<void> payFromAccount(String code) async {
    final dio = ref.read(apiClientProvider).dio;
    await dio.post<Map<String, dynamic>>('/me/fees/$code/pay-from-savings/');
    await refresh();
  }

  /// Initie un paiement Mobile Money du frais → renvoie la réponse `/payments/init/`
  /// (à passer à TaraCheckoutLauncher).
  Future<Map<String, dynamic>?> initMobileMoney({
    required String code,
    required String phone,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    final type =
        code == 'ADHESION' ? 'frais_adhesion' : 'frais_inscription';
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {'type': type, 'phone': phone, 'network': 'MTN'},
    );
    return res.data;
  }
}

final membershipFeesProvider =
    AsyncNotifierProvider<MembershipFeesNotifier, MembershipFeesState>(
  MembershipFeesNotifier.new,
);
