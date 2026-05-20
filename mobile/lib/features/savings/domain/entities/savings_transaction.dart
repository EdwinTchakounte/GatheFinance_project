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
}
