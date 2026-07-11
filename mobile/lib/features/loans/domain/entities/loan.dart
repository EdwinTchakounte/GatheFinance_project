import 'package:flutter/foundation.dart';

import '../loan_terms.dart';
import 'loan_installment.dart';

enum LoanStatus { actif, enRetard, cloture, contentieux }

/// CH-11 — Mode de retenue des intérêts (Sinora §5.3).
///
/// * [echeances] : intérêts répartis sur les échéances (comportement historique).
/// * [source] : intérêts retenus à la mise à disposition. Le membre reçoit 90 %
///   du nominal et ne rembourse que ce qu'il a touché.
enum LoanInterestMode { echeances, source }

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
    this.dateButoire,
    this.modeRetenueInterets = LoanInterestMode.echeances,
    this.montantDecaisseNet,
    this.interetsRetenusSource,
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

  /// CH-8 — Date butoire formelle pour solder le crédit. Les échéances sont
  /// indicatives ; seule la date butoire engage. Modifiable côté admin
  /// (extension exceptionnelle avec motif). Null = crédit legacy pre-CH-8.
  final DateTime? dateButoire;

  /// CH-11 — Mode de retenue des intérêts (figé à l'approbation).
  final LoanInterestMode modeRetenueInterets;

  /// CH-11 — Montant réellement versé au membre. En mode source = montant × 0.9.
  /// En mode echeances = montant nominal. Null = crédit legacy.
  final num? montantDecaisseNet;

  /// CH-11 — Intérêts ponctionnés à T0 par la coop (mode source uniquement).
  final num? interetsRetenusSource;

  LoanInstallment? get nextDue =>
      installments.where((i) => i.statut != InstallmentStatus.payee).firstOrNull;

  int get installmentsPayees =>
      installments.where((i) => i.statut == InstallmentStatus.payee).length;

  /// Progression du remboursement = part du MONTANT remboursé sur le total dû.
  /// Basé sur les montants (pas le nombre d'échéances payées) : avec la réforme
  /// 2026 il n'y a qu'une échéance (date butoir unique), donc un remboursement
  /// PARTIEL doit se refléter proportionnellement (ex. 3 000/5 000 → 60 %).
  double get progression {
    if (montantTotalDu <= 0) return 0;
    final rembourse = montantTotalDu - soldeRestant;
    return (rembourse / montantTotalDu).clamp(0.0, 1.0);
  }

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
          i.statut != InstallmentStatus.payee && i.dateEcheance.isBefore(now),)
      .toList();

  /// Pénalité de retard totale exigible à [now] = 50 % des intérêts de chaque
  /// échéance en retard (Article 12).
  num penaltyDue(DateTime now) => overdueInstallments(now)
      .fold<num>(0, (s, i) => s + latePenalty(i.montantInterets));
}
