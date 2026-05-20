import 'package:flutter/foundation.dart';

import 'loan_installment.dart';

enum LoanStatus { actif, enRetard, cloture, contentieux }

@immutable
class Loan {
  const Loan({
    required this.id,
    required this.numeroDossier,
    required this.montant,
    required this.tauxInteret,
    required this.dureeMois,
    required this.dateDecaissement,
    required this.datePremiereEcheance,
    required this.montantTotalDu,
    required this.soldeRestant,
    required this.statut,
    required this.installments,
  });

  final int id;
  final String numeroDossier;
  final num montant;
  final num tauxInteret;
  final int dureeMois;
  final DateTime dateDecaissement;
  final DateTime datePremiereEcheance;
  final num montantTotalDu;
  final num soldeRestant;
  final LoanStatus statut;
  final List<LoanInstallment> installments;

  LoanInstallment? get nextDue =>
      installments.where((i) => i.statut != InstallmentStatus.payee).firstOrNull;

  int get installmentsPayees =>
      installments.where((i) => i.statut == InstallmentStatus.payee).length;

  double get progression =>
      installments.isEmpty ? 0 : installmentsPayees / installments.length;
}
