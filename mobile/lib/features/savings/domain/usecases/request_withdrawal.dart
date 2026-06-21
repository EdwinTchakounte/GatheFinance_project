import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/withdrawal_request.dart';
import '../repositories/savings_repository.dart';

@immutable
class RequestWithdrawalParams {
  const RequestWithdrawalParams({
    required this.amount,
    required this.motif,
    required this.channel,
    this.recipientPhone = '',
    this.network,
  });

  final num amount;
  final String motif;
  final WithdrawalChannel channel;
  final String recipientPhone;
  final MomoNetwork? network;
}

class RequestWithdrawal
    extends UseCase<WithdrawalRequest, RequestWithdrawalParams> {
  const RequestWithdrawal(this._repo);
  final SavingsRepository _repo;

  @override
  Future<WithdrawalRequest> call(RequestWithdrawalParams params) async {
    if (params.amount < 500) {
      throw const ValidationFailure(
        'Le minimum de retrait est 500 XAF.',
        field: 'amount',
      );
    }
    if (params.channel == WithdrawalChannel.momo) {
      if (params.recipientPhone.trim().length < 8) {
        throw const ValidationFailure(
          'Numéro Mobile Money requis pour ce canal.',
          field: 'recipient_phone',
        );
      }
      if (params.network == null) {
        throw const ValidationFailure(
          'Réseau Mobile Money requis pour ce canal.',
          field: 'network',
        );
      }
    }
    return _repo.requestWithdrawal(
      amount: params.amount,
      motif: params.motif.trim(),
      channel: params.channel,
      recipientPhone: params.recipientPhone.trim(),
      network: params.network,
    );
  }
}

class ListMyWithdrawals
    extends UseCase<List<WithdrawalRequest>, NoParams> {
  const ListMyWithdrawals(this._repo);
  final SavingsRepository _repo;

  @override
  Future<List<WithdrawalRequest>> call(NoParams params) {
    return _repo.listMyWithdrawals();
  }
}
