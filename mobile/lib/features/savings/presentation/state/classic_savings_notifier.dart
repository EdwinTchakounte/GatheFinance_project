import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/usecases/deposit_savings.dart';

/// État du **compte épargne classique** (dissocié de la cotisation).
/// Même usecases que l'épargne, mais branchés sur le dépôt classique.
class ClassicSavingsNotifier extends AsyncNotifier<SavingsAccount> {
  late final _getMy = ref.read(getMyClassicSavingsUseCaseProvider);
  late final _deposit = ref.read(depositClassicSavingsUseCaseProvider);

  @override
  Future<SavingsAccount> build() => _getMy.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _getMy.call(const NoParams()));
  }

  /// CH-3 — [isPlacement] : sous-canal placement (bloqué 12 mois, rapporte
  /// un intérêt à maturité). Par défaut `false` = épargne libre.
  Future<void> deposit({
    required num amount,
    required String phone,
    required String network,
    bool isPlacement = false,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _deposit.call(
        DepositSavingsParams(
          amount: amount,
          phone: phone,
          network: network,
          isPlacement: isPlacement,
        ),
      ),
    );
  }
}

final classicSavingsProvider =
    AsyncNotifierProvider<ClassicSavingsNotifier, SavingsAccount>(
  ClassicSavingsNotifier.new,
);
