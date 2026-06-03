import 'package:flutter/foundation.dart';

import '../loan_terms.dart';
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
    this.dejaReconduit = false,
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

  /// Vrai si ce crédit a déjà été reconduit (Article 11 : une seule
  /// reconduction par crédit, bloquée même à la soumission).
  final bool dejaReconduit;

  LoanInstallment? get nextDue =>
      installments.where((i) => i.statut != InstallmentStatus.payee).firstOrNull;

  int get installmentsPayees =>
      installments.where((i) => i.statut == InstallmentStatus.payee).length;

  double get progression =>
      installments.isEmpty ? 0 : installmentsPayees / installments.length;

  /// Capital restant dû, réparti au prorata du payé sur chaque échéance.
  /// Base de calcul des intérêts de reconduction (Article 11) — le taux ne
  /// porte que sur le capital, jamais sur les intérêts (pas d'intérêt sur
  /// intérêt).
  num get capitalRestant => installments.fold<num>(0, (s, i) {
        final ratioPaye =
            i.montantTotal == 0 ? 0 : i.montantPaye / i.montantTotal;
        return s + i.montantCapital * (1 - ratioPaye);
      });

  /// Intérêts restant à courir, au prorata du payé sur chaque échéance.
  num get interetsRestants => installments.fold<num>(0, (s, i) {
        final ratioPaye =
            i.montantTotal == 0 ? 0 : i.montantPaye / i.montantTotal;
        return s + i.montantInterets * (1 - ratioPaye);
      });

  /// Échéances échues et non soldées à [now]. Cible de la pénalité de retard
  /// (Article 12).
  List<LoanInstallment> overdueInstallments(DateTime now) => installments
      .where((i) =>
          i.statut != InstallmentStatus.payee && i.dateEcheance.isBefore(now))
      .toList();

  /// Pénalité de retard totale exigible à [now] = 50 % des intérêts de chaque
  /// échéance en retard (Article 12).
  num penaltyDue(DateTime now) => overdueInstallments(now)
      .fold<num>(0, (s, i) => s + latePenalty(i.montantInterets));
}
