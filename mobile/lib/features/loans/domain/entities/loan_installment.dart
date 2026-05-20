import 'package:flutter/foundation.dart';

enum InstallmentStatus { aVenir, payee, enRetard, partielle }

@immutable
class LoanInstallment {
  const LoanInstallment({
    required this.id,
    required this.numero,
    required this.dateEcheance,
    required this.montantCapital,
    required this.montantInterets,
    required this.montantTotal,
    required this.montantPaye,
    required this.statut,
  });

  final int id;
  final int numero;
  final DateTime dateEcheance;
  final num montantCapital;
  final num montantInterets;
  final num montantTotal;
  final num montantPaye;
  final InstallmentStatus statut;

  num get restantDu => montantTotal - montantPaye;
}
