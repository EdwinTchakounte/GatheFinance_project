import 'package:flutter/foundation.dart';

enum LoanRequestStatus {
  enAttente, // frais d'étude pas encore payés
  enInstruction, // comité examine
  enAttenteAcceptationMembre, // contre-proposition à valider
  // CH-6 — Double approbation : provisoire (comité) → visite terrain (staff)
  // → décision définitive.
  approuveeProvisoire,
  approuvee,
  rejetee,
  // §7.2 LOT 10 — Voie AVALISTE : la demande attend la décision de l'avaliste
  // désigné (mail/notif envoyé, in-app accept/refuse).
  enAttenteAvaliste,
  rejeteeAvaliste, // l'avaliste a refusé (terminal, le membre peut désigner un autre)
  // §8 LOT 11 — Voie CAMPAGNE : la demande attend la validation activité
  // de la campagne par le comité.
  enValidationCampagne,
  rejeteeCampagne, // l'activité ne correspond pas au profil ciblé
  // §6 LOT 8 — Funding 24h : aucun prêteur n'a couvert la demande dans
  // les délais (la coop doit décider d'utiliser ses fonds ou de prolonger).
  enAttenteFunding,
}

/// Voie d'éligibilité empruntée (§6 BUSINESS_RULES_2026).
enum LoanRoute {
  seniorBrc, // collecte ≥ ratio . capital propre coop
  avaliste, // caution senior+BRC
  campagne, // microcampagne avec prêteurs
  garantieMaterielle, // L4 . bien matériel proposé en garantie
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
    this.route,
    this.dateLimiteEtude,
    this.fraisEtudeMontant,
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

  // §6 — Voie empruntée (BRC / avaliste / campagne). Peut être null pour
  // les demandes legacy ou tant que le backend ne l'a pas decidee.
  final LoanRoute? route;

  // L6 — Échéance indicative d'étude de la commission (soumission + ~1 mois).
  // Peut être null pour les demandes legacy antérieures au calcul backend.
  final DateTime? dateLimiteEtude;

  // CH-7 — Frais d'étude applicables (pilotés admin). Sert au « payer plus
  // tard » pour afficher/régler le bon montant. Null si non configuré.
  final num? fraisEtudeMontant;
}
