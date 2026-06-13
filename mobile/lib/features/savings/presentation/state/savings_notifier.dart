import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/usecases/deposit_savings.dart';

class SavingsNotifier extends AsyncNotifier<SavingsAccount> {
  late final _getMy = ref.read(getMySavingsUseCaseProvider);
  late final _deposit = ref.read(depositSavingsUseCaseProvider);

  @override
  Future<SavingsAccount> build() => _getMy.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _getMy.call(const NoParams()));
  }

  /// Lance un dépôt — émet `loading` puis `data` ou `error`.
  ///
  /// LOT 6 — [nbJoursCouverts] > 1 active le mode multi-jours pré-payé sur
  /// la collecte journalière. Le backend valide montant = nb × min_per_day
  /// et plafonne à 30 jours.
  Future<void> deposit({
    required num amount,
    required String phone,
    required String network,
    int nbJoursCouverts = 1,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _deposit.call(
        DepositSavingsParams(
          amount: amount,
          phone: phone,
          network: network,
          nbJoursCouverts: nbJoursCouverts,
        ),
      ),
    );
  }
}

final savingsProvider =
    AsyncNotifierProvider<SavingsNotifier, SavingsAccount>(SavingsNotifier.new);
