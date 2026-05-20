import 'package:flutter/foundation.dart';

import 'savings_transaction.dart';

@immutable
class SavingsAccount {
  const SavingsAccount({
    required this.id,
    required this.solde,
    required this.dateOuverture,
    required this.tauxInteret,
    required this.transactions,
  });

  final int id;
  final num solde;
  final DateTime dateOuverture;
  final num tauxInteret;
  final List<SavingsTransaction> transactions;

  /// Copie immuable avec valeurs surchargées — utilisée pour les optimistic
  /// updates côté presentation (ex. dépôt simulé).
  SavingsAccount copyWith({
    num? solde,
    List<SavingsTransaction>? transactions,
  }) {
    return SavingsAccount(
      id: id,
      solde: solde ?? this.solde,
      dateOuverture: dateOuverture,
      tauxInteret: tauxInteret,
      transactions: transactions ?? this.transactions,
    );
  }
}
