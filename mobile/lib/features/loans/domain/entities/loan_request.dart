import 'package:flutter/foundation.dart';

enum LoanRequestStatus {
  enAttente, // frais pas encore payés
  enInstruction, // comité examine
  enAttenteAcceptationMembre, // contre-proposition à valider
  // CH-6 — Double approbation : provisoire (comité) → visite terrain (staff)
  // → décision définitive.
  approuveeProvisoire,
  approuvee,
  rejetee,
}

/// CH-9 — Canal de réception choisi par le membre à la soumission.
/// Pilote l'auto-fill du payout Tara à la mise à disposition.
enum LoanReceiveChannel {
  taraOm,
  taraMomo,
  agenceEspeces,
}

/// CH-6 — Verdict de la visite terrain (entre approbation provisoire et
/// décision définitive du comité).
enum FieldVisitOutcome {
  favorable,
  defavorable,
  aRevoir,
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
    this.moyenReception,
    this.recipientPhone,
    this.fieldVisitOutcome,
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

  // CH-9 — Moyen de réception (peut être null pour les demandes legacy
  // soumises avant le chantier juin 2026).
  final LoanReceiveChannel? moyenReception;
  final String? recipientPhone;

  // CH-6 — Verdict visite terrain (null tant que pas posé).
  final FieldVisitOutcome? fieldVisitOutcome;
}
