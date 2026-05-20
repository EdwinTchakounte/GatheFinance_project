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
  Future<void> deposit({
    required num amount,
    required String phone,
    required String network,
  }) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(
      () => _deposit.call(
        DepositSavingsParams(amount: amount, phone: phone, network: network),
      ),
    );
  }
}

final savingsProvider =
    AsyncNotifierProvider<SavingsNotifier, SavingsAccount>(SavingsNotifier.new);
