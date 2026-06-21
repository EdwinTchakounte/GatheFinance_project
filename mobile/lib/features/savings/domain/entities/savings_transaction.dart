import 'package:flutter/foundation.dart';

enum SavingsType { depot, retrait, interet }

@immutable
class SavingsTransaction {
  const SavingsTransaction({
    required this.id,
    required this.type,
    required this.montant,
    required this.soldeApres,
    required this.date,
  });

  final int id;
  final SavingsType type;
  final num montant;
  final num soldeApres;
  final DateTime date;

  Map<String, Object?> toJson() => {
        'id': id,
        'type_op': type.name,
        'montant': montant,
        'solde_apres': soldeApres,
        'date': date.toIso8601String(),
      };

  static SavingsTransaction fromJson(Map<String, dynamic> json) {
    SavingsType parseType(String raw) => switch (raw) {
          'retrait' => SavingsType.retrait,
          'interet' => SavingsType.interet,
          _ => SavingsType.depot,
        };
    return SavingsTransaction(
      id: (json['id'] as num?)?.toInt() ?? 0,
      type: parseType((json['type_op'] as String?) ?? 'depot'),
      montant: (json['montant'] as num?) ?? 0,
      soldeApres: (json['solde_apres'] as num?) ?? 0,
      date: DateTime.tryParse((json['date'] as String?) ?? '') ??
          DateTime.now(),
    );
  }
}
