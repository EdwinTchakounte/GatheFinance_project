import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/cache/snapshot_store.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../../../core/utils/pollable_notifier.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/usecases/deposit_savings.dart';

const _classicCacheKey = 'savings_classic_me';

/// État du **compte épargne classique** (dissocié de la cotisation).
/// Même usecases que l'épargne, mais branchés sur le dépôt classique.
class ClassicSavingsNotifier extends AsyncNotifier<SavingsAccount>
    with PollableAsyncNotifier<SavingsAccount> {
  late final _getMy = ref.read(getMyClassicSavingsUseCaseProvider);
  late final _deposit = ref.read(depositClassicSavingsUseCaseProvider);

  Future<SavingsAccount> _fetch() async {
    try {
      return await _getMy.call(const NoParams());
    } catch (e) {
      final cached = await SnapshotStore.load(_classicCacheKey);
      if (cached == null) rethrow;
      return SavingsAccount.fromJson(cached.data as Map<String, dynamic>)
          .copyWith(cachedAt: cached.savedAt);
    }
  }

  Future<void> _persist(SavingsAccount acc) async {
    if (acc.cachedAt != null) return;
    await SnapshotStore.save(_classicCacheKey, acc.toJson());
  }

  @override
  Future<SavingsAccount> build() async {
    final acc = await _fetch();
    seedPollHash(acc);
    await _persist(acc);
    return acc;
  }

  Future<void> refresh() => silentRefresh(
        _fetch,
        onFreshData: (acc) => unawaited(_persist(acc)),
      );

  /// CH-3 . [isPlacement] : sous-canal placement (bloqué 12 mois, rapporte
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
