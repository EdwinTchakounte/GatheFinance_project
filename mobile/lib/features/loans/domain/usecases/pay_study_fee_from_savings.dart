import 'package:flutter/foundation.dart';

import '../../../../core/usecases/usecase.dart';
import '../repositories/loans_repository.dart';

@immutable
class PayStudyFeeFromSavingsParams {
  const PayStudyFeeFromSavingsParams({required this.requestId});

  final int requestId;
}

/// Porte des frais 2026 — règle les frais d'étude sur l'épargne classique.
///
/// C'est le canal proposé par défaut. Contrairement à [PayLoanRequestStudyFee],
/// il n'y a aucun numéro à valider ici : c'est un transfert interne, donc
/// synchrone (ni Tara, ni webhook, ni polling). Au retour, la demande a déjà
/// changé de statut.
///
/// Le backend reste seul juge du disponible : il refuse (409) si le retirable
/// ne couvre pas les frais. On ne duplique pas cette règle ici — le placement
/// et l'épargne gelée en garantie ne sont pas ponctionnables, et cette
/// arithmétique n'a pas à vivre en deux exemplaires.
class PayStudyFeeFromSavings
    extends UseCase<void, PayStudyFeeFromSavingsParams> {
  const PayStudyFeeFromSavings(this._repo);
  final LoansRepository _repo;

  @override
  Future<void> call(PayStudyFeeFromSavingsParams params) =>
      _repo.payStudyFeeFromSavings(requestId: params.requestId);
}
