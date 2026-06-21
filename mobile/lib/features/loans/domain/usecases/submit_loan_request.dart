import 'package:flutter/foundation.dart';

import '../../../../core/error/failures.dart';
import '../../../../core/usecases/usecase.dart';
import '../entities/loan_request.dart';
import '../entities/loan_request_submission.dart';
import '../repositories/loans_repository.dart';

@immutable
class SubmitLoanRequestParams {
  const SubmitLoanRequestParams({
    required this.montantDemande,
    required this.dureeMois,
    required this.motif,
    this.moyenReception,
    this.recipientPhone,
    this.extraValues = const {},
  });

  final num montantDemande;
  final int dureeMois;
  final String motif;
  // CH-9 — Canal de réception choisi par le membre (optionnel pour rétro-compat).
  final LoanReceiveChannel? moyenReception;
  final String? recipientPhone;
  // CH-5 — Champs scalaires extra du FormSchema actif (loan_request).
  final Map<String, Object?> extraValues;
}

class SubmitLoanRequest
    extends UseCase<LoanRequestSubmission, SubmitLoanRequestParams> {
  const SubmitLoanRequest(this._repo);
  final LoansRepository _repo;

  static const int _dureeMin = 3;
  static const int _dureeMax = 36;
  static const num _montantMin = 50000;

  @override
  Future<LoanRequestSubmission> call(SubmitLoanRequestParams params) async {
    if (params.montantDemande < _montantMin) {
      throw const ValidationFailure(
        'Montant minimum 50 000 XAF.',
        field: 'montant',
      );
    }
    if (params.dureeMois < _dureeMin || params.dureeMois > _dureeMax) {
      throw const ValidationFailure(
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
    // CH-9 — Quand le canal est Tara MoMo / OM, le téléphone est requis.
    final phone = params.recipientPhone?.trim() ?? '';
    final needsPhone = params.moyenReception == LoanReceiveChannel.taraOm ||
        params.moyenReception == LoanReceiveChannel.taraMomo;
    if (needsPhone && phone.length < 9) {
      throw const ValidationFailure(
        'Numéro Mobile Money requis pour un décaissement Tara.',
        field: 'recipient_phone',
      );
    }
    return _repo.submitRequest(
      montantDemande: params.montantDemande,
      dureeMois: params.dureeMois,
      motif: params.motif.trim(),
      moyenReception: params.moyenReception,
      recipientPhone: needsPhone ? phone : null,
      extraValues: params.extraValues,
    );
  }
}
