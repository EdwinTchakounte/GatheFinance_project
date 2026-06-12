import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/savings_account.dart';
import '../repositories/savings_repository.dart';

@immutable
class DepositSavingsParams {
  const DepositSavingsParams({
    required this.amount,
    required this.phone,
    required this.network,
    this.isPlacement = false,
  });

  final num amount;
  final String phone;
  final String network;
  // CH-3 — Sous-canal placement (épargne classique uniquement).
  final bool isPlacement;
}

class DepositSavings extends UseCase<SavingsAccount, DepositSavingsParams> {
  const DepositSavings(this._repo);
  final SavingsRepository _repo;

  @override
  Future<SavingsAccount> call(DepositSavingsParams params) async {
    if (params.amount < 100) {
      throw const ValidationFailure('Le minimum est 100 XAF.', field: 'amount');
    }
    return _repo.deposit(
      amount: params.amount,
      phone: params.phone,
      network: params.network,
      isPlacement: params.isPlacement,
    );
  }
}
