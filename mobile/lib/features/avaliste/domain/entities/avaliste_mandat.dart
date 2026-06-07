import 'package:flutter/foundation.dart';

enum AvalisteStatut { pending, accepted, refused }

/// Demandeur résumé — l'avaliste a besoin de savoir qui le sollicite.
@immutable
class AvalisteDemandeur {
  const AvalisteDemandeur({
    required this.id,
    required this.numeroMembre,
    required this.prenom,
    required this.nom,
  });

  final int id;
  final String numeroMembre;
  final String prenom;
  final String nom;

  String get fullName => '$prenom $nom';
}

/// Snapshot couverture épargne (au moment de la demande) — affiche à
/// l'avaliste si sa propre épargne est suffisante (ratio ≥ 1 = ok).
@immutable
class AvalisteCouverture {
  const AvalisteCouverture({
    required this.epargneBorrower,
    required this.epargneAvaliste,
    required this.ratio,
  });

  final num epargneBorrower;
  final num epargneAvaliste;

  /// Ratio = epargne_avaliste / montant_demandé (>= 1 = couvre).
  final num ratio;
}

/// Demande de crédit à laquelle l'avaliste est attaché.
@immutable
class AvalisteLoanRequest {
  const AvalisteLoanRequest({
    required this.id,
    required this.montantDemande,
    required this.dureeMois,
    required this.motif,
    required this.statut,
    required this.dateSoumission,
  });

  final int id;
  final num montantDemande;
  final int dureeMois;
  final String motif;
  final String statut;
  final DateTime dateSoumission;
}

/// Mandat d'avaliste (LOT 18 refonte 2026) — l'avaliste accepte ou refuse
/// d'être garant pour la demande de crédit d'un autre membre.
@immutable
class AvalisteMandat {
  const AvalisteMandat({
    required this.id,
    required this.statut,
    required this.statutDisplay,
    required this.respondedAt,
    required this.refusMotif,
    required this.createdAt,
    required this.demandeur,
    required this.loanRequest,
    required this.couverture,
  });

  final int id;
  final AvalisteStatut statut;
  final String statutDisplay;
  final DateTime? respondedAt;
  final String refusMotif;
  final DateTime createdAt;
  final AvalisteDemandeur demandeur;
  final AvalisteLoanRequest loanRequest;
  final AvalisteCouverture couverture;

  bool get isPending => statut == AvalisteStatut.pending;
  bool get isAccepted => statut == AvalisteStatut.accepted;
  bool get isRefused => statut == AvalisteStatut.refused;
}

/// Résultat de [list] côté backend — porte aussi le compteur pending pour
/// l'UI (badge sur le bouton du menu Crédit).
@immutable
class AvalisteMandatList {
  const AvalisteMandatList({required this.items, required this.pendingCount});
  final List<AvalisteMandat> items;
  final int pendingCount;
}
