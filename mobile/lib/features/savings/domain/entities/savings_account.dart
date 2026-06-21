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
    this.cachedAt,
  });

  final int id;
  final num solde;
  final DateTime dateOuverture;
  final num tauxInteret;
  final List<SavingsTransaction> transactions;

  /// Quand on a chargé ce snapshot depuis le cache local (offline fallback).
  /// `null` quand la donnée vient d'un fetch réseau frais. L'UI affiche une
  /// bannière "données du XX/XX à HH:MM" si non null.
  final DateTime? cachedAt;

  /// Copie immuable avec valeurs surchargées — utilisée pour les optimistic
  /// updates côté presentation (ex. dépôt simulé).
  SavingsAccount copyWith({
    num? solde,
    List<SavingsTransaction>? transactions,
    DateTime? cachedAt,
  }) {
    return SavingsAccount(
      id: id,
      solde: solde ?? this.solde,
      dateOuverture: dateOuverture,
      tauxInteret: tauxInteret,
      transactions: transactions ?? this.transactions,
      cachedAt: cachedAt ?? this.cachedAt,
    );
  }

  Map<String, Object?> toJson() => {
        'id': id,
        'solde': solde,
        'date_ouverture': dateOuverture.toIso8601String(),
        'taux_interet': tauxInteret,
        'transactions': transactions.map((t) => t.toJson()).toList(),
      };

  static SavingsAccount fromJson(Map<String, dynamic> json) {
    return SavingsAccount(
      id: (json['id'] as num?)?.toInt() ?? 0,
      solde: (json['solde'] as num?) ?? 0,
      dateOuverture:
          DateTime.tryParse((json['date_ouverture'] as String?) ?? '') ??
              DateTime.now(),
      tauxInteret: (json['taux_interet'] as num?) ?? 0,
      transactions: ((json['transactions'] as List?) ?? const [])
          .map((e) => SavingsTransaction.fromJson(e as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
