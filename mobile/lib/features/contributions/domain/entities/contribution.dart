import 'package:flutter/foundation.dart';

/// Types canoniques de paiements/cotisations remontés par le backend
/// (apps_coop/payments/models.py → `Payment.Type`).
enum ContributionType {
  fraisInscription,
  fraisAdhesion,
  fraisDemandeCredit,
  fraisReconduction,
  fraisCarnet,
}

enum ContributionStatus { valide, enAttente, echec }

@immutable
class Contribution {
  const Contribution({
    required this.id,
    required this.type,
    required this.montant,
    required this.statut,
    required this.date,
    this.reference,
  });

  final int id;
  final ContributionType type;
  final num montant;
  final ContributionStatus statut;
  final DateTime date;
  final String? reference;
}
