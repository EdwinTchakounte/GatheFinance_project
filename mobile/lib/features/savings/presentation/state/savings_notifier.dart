import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/cache/snapshot_store.dart';
import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../../../core/utils/pollable_notifier.dart';
import '../../domain/entities/savings_account.dart';
import '../../domain/usecases/deposit_savings.dart';

const _savingsCacheKey = 'savings_cotisation_me';

class SavingsNotifier extends AsyncNotifier<SavingsAccount>
    with PollableAsyncNotifier<SavingsAccount> {
  late final _getMy = ref.read(getMySavingsUseCaseProvider);
  late final _deposit = ref.read(depositSavingsUseCaseProvider);

  /// Fetch live avec fallback snapshot offline. Ne persiste RIEN ici : la
  /// persistance est déclenchée par le caller uniquement sur donnée fraîche.
  Future<SavingsAccount> _fetch() async {
    try {
      return await _getMy.call(const NoParams());
    } catch (e) {
      final cached = await SnapshotStore.load(_savingsCacheKey);
      if (cached == null) rethrow;
      return SavingsAccount.fromJson(cached.data as Map<String, dynamic>)
          .copyWith(cachedAt: cached.savedAt);
    }
  }

  /// Persiste le snapshot offline UNIQUEMENT pour une donnée live (pas un
  /// snapshot rechargé du cache) et seulement quand elle a changé (le caller
  /// ne nous appelle que sur donnée fraîche).
  Future<void> _persist(SavingsAccount acc) async {
    if (acc.cachedAt != null) return; // vient déjà du cache : rien à réécrire.
    await SnapshotStore.save(_savingsCacheKey, acc.toJson());
  }

  @override
  Future<SavingsAccount> build() async {
    final acc = await _fetch();
    seedPollHash(acc);
    await _persist(acc);
    return acc;
  }

  /// Rafraîchissement silencieux (polling) : garde la donnée affichée, ne
  /// repousse le state + ne réécrit le snapshot que si le contenu a changé.
  Future<void> refresh() => silentRefresh(
        _fetch,
        onFreshData: (acc) => unawaited(_persist(acc)),
      );

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
