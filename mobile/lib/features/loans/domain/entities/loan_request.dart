import 'package:flutter/foundation.dart';

enum LoanRequestStatus {
  enAttente, // frais pas encore payés
  enInstruction, // comité examine
  enAttenteAcceptationMembre, // contre-proposition à valider
  approuvee,
  rejetee,
}

@immutable
class LoanRequestEntity {
  const LoanRequestEntity({
    required this.id,
    required this.montantDemande,
    required this.dureeMois,
    required this.motif,
    required this.statut,
    required this.dateSoumission,
    this.dateDecision,
    this.motifRejet = '',
    this.montantRevise,
    this.dureeRevisee,
  });

  final int id;
  final num montantDemande;
  final int dureeMois;
  final String motif;
  final LoanRequestStatus statut;
  final DateTime dateSoumission;
  final DateTime? dateDecision;
  final String motifRejet;
  final num? montantRevise;
  final int? dureeRevisee;
}
