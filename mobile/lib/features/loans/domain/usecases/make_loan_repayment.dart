import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/loan.dart';
import '../repositories/loans_repository.dart';

@immutable
class MakeLoanRepaymentParams {
  const MakeLoanRepaymentParams({
    required this.loanId,
    required this.montant,
    required this.phone,
    required this.network,
  });

  final int loanId;
  final num montant;
  final String phone;
  final String network;
}

class MakeLoanRepayment extends UseCase<Loan, MakeLoanRepaymentParams> {
  const MakeLoanRepayment(this._repo);
  final LoansRepository _repo;

  @override
  Future<Loan> call(MakeLoanRepaymentParams params) async {
    if (params.montant < 100) {
      throw const ValidationFailure(
        'Le minimum est 100 XAF.',
        field: 'montant',
      );
    }
    return _repo.repay(
      loanId: params.loanId,
      montant: params.montant,
      phone: params.phone,
      network: params.network,
    );
  }
}
