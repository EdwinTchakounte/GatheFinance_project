import 'package:flutter/foundation.dart';

import '../loan_terms.dart';

enum LoanRenewalStatus { demandee, approuvee, rejetee }

/// Demande de reconduction d'un crédit (Articles 9-11).
///
/// La prorogation est fixe (+1 mois, Article 10). Le membre choisit le mode :
///  - [comptant] = true  → verse les intérêts au comptant → taux 10 %
///  - [comptant] = false → intérêts reportés avec le capital → taux 15 %
/// Les intérêts de reconduction portent uniquement sur le capital restant.
@immutable
class LoanRenewalEntity {
  const LoanRenewalEntity({
    required this.id,
    required this.loanId,
    required this.comptant,
    required this.capitalRestant,
    required this.interetsReconduction,
    required this.statut,
    required this.dateDemande,
    this.dateDecision,
  });

  final int id;
  final int loanId;

  /// Mode de reconduction (Article 11) : true = au comptant (10 %).
  final bool comptant;

  /// Capital restant dû au moment de la demande (base des intérêts).
  final num capitalRestant;

  /// Intérêts de reconduction = taux × capital restant.
  final num interetsReconduction;

  final LoanRenewalStatus statut;
  final DateTime dateDemande;
  final DateTime? dateDecision;

  /// Prorogation accordée (Article 10) — toujours +1 mois.
  int get prorogationMois => kRenewalExtraMonths;
}
