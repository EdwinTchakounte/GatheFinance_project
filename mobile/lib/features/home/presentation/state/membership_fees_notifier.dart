import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';

/// Un des trois frais d'activation (adhésion / inscription / carnet).
class MembershipFee {
  const MembershipFee({
    required this.code,
    required this.amount,
    required this.solvable,
    required this.paye,
  });

  final String code; // ADHESION | INSCRIPTION | CARNET
  final num amount;
  final bool solvable; // réglable depuis l'épargne (compte solvable)
  final bool paye; // déjà réglé (paiement validé)

  String get label => switch (code) {
        'ADHESION' => "Frais d'adhésion",
        'INSCRIPTION' => "Frais d'inscription",
        'CARNET' => 'Frais de carnet',
        _ => code,
      };

  /// Type `Payment` backend correspondant (pour `/payments/init/`).
  String get paymentType => switch (code) {
        'ADHESION' => 'frais_adhesion',
        'INSCRIPTION' => 'frais_inscription',
        'CARNET' => 'frais_carnet',
        _ => 'frais_adhesion',
      };
}

/// Statut des trois frais d'activation : montants, solvabilité, déjà réglé, et
/// statut du membre. Alimente l'écran d'activation mobile (parité portail).
class MembershipFeesState {
  const MembershipFeesState({
    required this.statut,
    required this.available,
    required this.fees,
  });

  final String statut;
  final num available;
  final List<MembershipFee> fees;

  bool get isActive => statut == 'actif';

  /// Frais réellement dus (montant > 0), dans l'ordre d'affichage.
  List<MembershipFee> get due => fees.where((f) => f.amount > 0).toList();
  num get total => due.fold<num>(0, (s, f) => s + f.amount);
  int get requiredCount => due.length;
  int get paidCount => due.where((f) => f.paye).length;
  bool get allPaid => requiredCount > 0 && paidCount == requiredCount;

  factory MembershipFeesState.fromJson(Map<String, dynamic> j) {
    final feesJson = (j['fees'] as Map<String, dynamic>? ?? const {});
    num p(Object? v) => num.tryParse('${v ?? 0}') ?? 0;
    MembershipFee parse(String code) {
      final f = (feesJson[code] as Map<String, dynamic>? ?? const {});
      return MembershipFee(
        code: code,
        amount: p(f['montant']),
        solvable: f['solvable'] == true,
        paye: f['paye'] == true,
      );
    }

    return MembershipFeesState(
      statut: j['statut'] as String? ?? '',
      available: p(j['available']),
      // Ordre d'affichage : adhésion → inscription → carnet.
      fees: [parse('ADHESION'), parse('INSCRIPTION'), parse('CARNET')],
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

  /// Initie un paiement Mobile Money du frais → renvoie la réponse
  /// `/payments/init/` (à passer à TaraCheckoutLauncher).
  Future<Map<String, dynamic>?> initMobileMoney({
    required String code,
    required String phone,
    num? montant,
  }) async {
    final dio = ref.read(apiClientProvider).dio;
    final type = switch (code) {
      'ADHESION' => 'frais_adhesion',
      'INSCRIPTION' => 'frais_inscription',
      'CARNET' => 'frais_carnet',
      _ => 'frais_adhesion',
    };
    // Le montant reste AUTORITAIRE côté serveur (barème FeeType) ; on l'envoie
    // quand même par robustesse. Réseau NON forcé : Tara détecte l'opérateur
    // depuis le préfixe du numéro (plus de « MTN » codé en dur qui cassait
    // Orange).
    final res = await dio.post<Map<String, dynamic>>(
      '/payments/init/',
      data: {
        'type': type,
        'phone': phone,
        if (montant != null && montant > 0) 'montant': montant,
      },
    );
    return res.data;
  }
}

final membershipFeesProvider =
    AsyncNotifierProvider<MembershipFeesNotifier, MembershipFeesState>(
  MembershipFeesNotifier.new,
);
