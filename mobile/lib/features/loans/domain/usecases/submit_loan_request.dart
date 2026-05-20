import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/loan_request.dart';
import '../repositories/loans_repository.dart';

@immutable
class SubmitLoanRequestParams {
  const SubmitLoanRequestParams({
    required this.montantDemande,
    required this.dureeMois,
    required this.motif,
  });

  final num montantDemande;
  final int dureeMois;
  final String motif;
}

class SubmitLoanRequest
    extends UseCase<LoanRequestEntity, SubmitLoanRequestParams> {
  const SubmitLoanRequest(this._repo);
  final LoansRepository _repo;

  static const int _dureeMin = 3;
  static const int _dureeMax = 36;
  static const num _montantMin = 50000;

  @override
  Future<LoanRequestEntity> call(SubmitLoanRequestParams params) async {
    if (params.montantDemande < _montantMin) {
      throw const ValidationFailure(
        'Montant minimum 50 000 XAF.',
        field: 'montant',
      );
    }
    if (params.dureeMois < _dureeMin || params.dureeMois > _dureeMax) {
      throw ValidationFailure(
        'Durée attendue entre $_dureeMin et $_dureeMax mois.',
        field: 'duree',
      );
    }
    if (params.motif.trim().length < 10) {
      throw const ValidationFailure(
        'Motivation trop courte — précise ton projet (min 10 caractères).',
        field: 'motif',
      );
    }
    return _repo.submitRequest(
      montantDemande: params.montantDemande,
      dureeMois: params.dureeMois,
      motif: params.motif.trim(),
    );
  }
}
