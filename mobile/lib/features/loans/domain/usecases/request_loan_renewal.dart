import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/loan_renewal.dart';
import '../repositories/loans_repository.dart';

@immutable
class RequestLoanRenewalParams {
  const RequestLoanRenewalParams({
    required this.loanId,
    required this.nouvelleDureeMois,
  });

  final int loanId;
  final int nouvelleDureeMois;
}

class RequestLoanRenewal
    extends UseCase<LoanRenewalEntity, RequestLoanRenewalParams> {
  const RequestLoanRenewal(this._repo);
  final LoansRepository _repo;

  static const int _dureeMin = 3;
  static const int _dureeMax = 36;

  @override
  Future<LoanRenewalEntity> call(RequestLoanRenewalParams params) async {
    if (params.nouvelleDureeMois < _dureeMin ||
        params.nouvelleDureeMois > _dureeMax) {
      throw ValidationFailure(
        'Durée attendue entre $_dureeMin et $_dureeMax mois.',
        field: 'duree',
      );
    }
    return _repo.requestRenewal(
      loanId: params.loanId,
      nouvelleDureeMois: params.nouvelleDureeMois,
    );
  }
}
