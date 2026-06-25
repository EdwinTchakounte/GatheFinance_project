import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/cache/snapshot_store.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/usecases/deposit_savings.dart';

const _savingsCacheKey = 'savings_cotisation_me';

class SavingsNotifier extends AsyncNotifier<SavingsAccount> {
  late final _getMy = ref.read(getMySavingsUseCaseProvider);
  late final _deposit = ref.read(depositSavingsUseCaseProvider);

  @override
  Future<SavingsAccount> build() async {
    // memory mobile cache-offline . on tente d'abord le fetch live ; en cas
    // d'échec réseau, on retombe sur le snapshot persistant pour que l'UI
    // reste utilisable hors connexion. Le snapshot est rafraîchi à chaque
    // fetch réussi.
    try {
      final live = await _getMy.call(const NoParams());
      await SnapshotStore.save(_savingsCacheKey, live.toJson());
      return live;
    } catch (e) {
      final cached = await SnapshotStore.load(_savingsCacheKey);
      if (cached == null) rethrow;
      return SavingsAccount.fromJson(cached.data as Map<String, dynamic>)
          .copyWith(cachedAt: cached.savedAt);
    }
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(build);
  }

  /// Lance un dépôt . émet `loading` puis `data` ou `error`.
  ///
  /// LOT 6 . [nbJoursCouverts] > 1 active le mode multi-jours pré-payé sur
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
