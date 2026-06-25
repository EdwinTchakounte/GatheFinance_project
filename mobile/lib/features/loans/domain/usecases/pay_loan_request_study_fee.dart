import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../repositories/loans_repository.dart';

@immutable
class PayLoanRequestStudyFeeParams {
  const PayLoanRequestStudyFeeParams({
    required this.phone,
    required this.network,
    this.montant,
  });

  final String phone;
  final String network;
  final int? montant;
}

/// CH-7 — Règle les frais d'étude d'une demande EN_ATTENTE via Mobile Money.
///
/// Validation locale du numéro (≥ 9 chiffres). Le réseau est laissé vide :
/// Tara détecte automatiquement MTN/Orange via le préfixe du téléphone.
/// Le backend identifie la LoanRequest cible par le membre courant — pas
/// besoin de transmettre l'identifiant de la demande.
class PayLoanRequestStudyFee
    extends UseCase<void, PayLoanRequestStudyFeeParams> {
  const PayLoanRequestStudyFee(this._repo);
  final LoansRepository _repo;

  @override
  Future<void> call(PayLoanRequestStudyFeeParams params) async {
    final phone = params.phone.trim();
    if (phone.length < 9) {
      throw const ValidationFailure(
        'Numéro Mobile Money requis (au moins 9 chiffres).',
        field: 'phone',
      );
    }
    await _repo.payStudyFee(
      phone: phone,
      network: params.network,
      montant: params.montant,
    );
  }
}
