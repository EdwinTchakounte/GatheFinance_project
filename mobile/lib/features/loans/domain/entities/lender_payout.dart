import 'package:flutter/foundation.dart';

/// CH-12 — Versement d'intérêts reçu par le membre en tant que prêteur.
///
/// * [LenderPayoutKind.atSource] : versement à T0 (mode CH-11 'source'),
///   crédité immédiatement au décaissement du crédit. Pas d'échéance attachée.
/// * [LenderPayoutKind.installment] : versement au fil des remboursements
///   (mode legacy 'echeances'), proportionnel à l'imputation intérêt d'une
///   échéance précise.
enum LenderPayoutKind { atSource, installment }

@immutable
class LenderPayout {
  const LenderPayout({
    required this.id,
    required this.montant,
    required this.date,
    required this.kind,
    required this.loanNumeroDossier,
    required this.loanId,
    required this.quotePart,
    this.installmentNumero,
  });

  final int id;
  final num montant;
  final DateTime date;
  final LenderPayoutKind kind;

  /// Référence du crédit financé.
  final String loanNumeroDossier;
  final int loanId;

  /// Fraction du crédit que représente la portion de ce prêteur (ex. 0.5).
  final num quotePart;

  /// Numéro de l'échéance qui a généré ce versement. Null en mode source.
  final int? installmentNumero;
}
