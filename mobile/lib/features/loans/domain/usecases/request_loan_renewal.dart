import 'package:flutter/foundation.dart';

import '../../../../core/usecases/usecase.dart';
import '../entities/loan_renewal.dart';
import '../repositories/loans_repository.dart';

@immutable
class RequestLoanRenewalParams {
  const RequestLoanRenewalParams({
    required this.loanId,
    required this.comptant,
  });

  final int loanId;

  /// Mode de reconduction (Article 11) : true = intérêts au comptant (10 %),
  /// false = intérêts reportés (15 %).
  final bool comptant;
}

/// Demande de reconduction (Articles 9-11).
///
/// La prorogation est fixe (+1 mois, Article 10) : aucune durée à valider côté
/// membre. Le blocage « une seule reconduction par crédit » (Article 11) est
/// appliqué à la source de données (le crédit déjà reconduit est rejeté).
class RequestLoanRenewal
    extends UseCase<LoanRenewalEntity, RequestLoanRenewalParams> {
  const RequestLoanRenewal(this._repo);
  final LoansRepository _repo;

  @override
  Future<LoanRenewalEntity> call(RequestLoanRenewalParams params) {
    return _repo.requestRenewal(
      loanId: params.loanId,
      comptant: params.comptant,
    );
  }
}
