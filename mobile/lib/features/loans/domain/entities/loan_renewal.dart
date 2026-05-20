import 'package:flutter/foundation.dart';

enum LoanRenewalStatus { demandee, approuvee, rejetee }

@immutable
class LoanRenewalEntity {
  const LoanRenewalEntity({
    required this.id,
    required this.loanId,
    required this.nouvelleDureeMois,
    required this.statut,
    required this.dateDemande,
    this.fraisPayes = false,
    this.dateDecision,
  });

  final int id;
  final int loanId;
  final int nouvelleDureeMois;
  final LoanRenewalStatus statut;
  final DateTime dateDemande;
  final bool fraisPayes;
  final DateTime? dateDecision;
}
