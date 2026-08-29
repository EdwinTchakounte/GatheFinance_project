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
    this.frais = 0,
    this.reference,
  });

  final int id;
  final ContributionType type;
  final num montant;
  // Frais de transaction (%) prélevés EN PLUS du montant lorsque le versement
  // passe par Tara (Mobile Money). 0 en agence / déduction épargne. Parité
  // avec le portail, qui affiche déjà « montant + frais = total payé ».
  final num frais;
  final ContributionStatus statut;
  final DateTime date;
  final String? reference;

  /// Total réellement débité au membre (ce qu'il a payé via Tara).
  num get totalPaye => montant + frais;
}
