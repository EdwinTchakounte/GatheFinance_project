import 'package:flutter/foundation.dart';

import '../../../../core/formatters/name_formatter.dart';

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

  String get fullName => nomComplet(prenom, nom);
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
    this.montantGele = 0,
    this.cniDemandeur = '',
    this.cniAvaliste = '',
    this.cniAvalisteFichier = '',
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

  /// Montant gelé sur l'épargne de l'avaliste au titre de cette garantie
  /// (refonte garantie 2026). 0 tant que le mandat n'est pas accepté / que le
  /// backend n'a rien gelé.
  final num montantGele;

  /// L5 identité . Numéros de CNI captés côté crédit (demandeur) et côté
  /// acceptation (avaliste), + l'URL du justificatif uploadé par l'avaliste.
  /// Vides tant que non renseignés côté backend.
  final String cniDemandeur;
  final String cniAvaliste;
  final String cniAvalisteFichier;

  bool get isPending => statut == AvalisteStatut.pending;
  bool get isAccepted => statut == AvalisteStatut.accepted;
  bool get isRefused => statut == AvalisteStatut.refused;

  /// Empreinte utilisée par `PollableNotifier` pour dédoublonner les
  /// rafraîchissements. SANS elle, le hash retombe sur `toString()`
  /// (« Instance of AvalisteMandat »), identique d'un poll à l'autre : un
  /// nouveau mandat ou un changement de statut n'était jamais poussé à
  /// l'écran de l'avaliste.
  Map<String, dynamic> toJson() => {
        'id': id,
        'statut': statut.name,
        'statut_display': statutDisplay,
        'responded_at': respondedAt?.toIso8601String(),
        'refus_motif': refusMotif,
        'created_at': createdAt.toIso8601String(),
        'demandeur_id': demandeur.id,
        'demandeur': demandeur.fullName,
        'loan_request_id': loanRequest.id,
        'loan_request_statut': loanRequest.statut,
        'montant_demande': montantDemande,
        'montant_gele': montantGele,
        'ratio': couverture.ratio,
        'cni_demandeur': cniDemandeur,
        'cni_avaliste': cniAvaliste,
        'cni_avaliste_fichier': cniAvalisteFichier,
      };

  num get montantDemande => loanRequest.montantDemande;
}

/// Résultat de [list] côté backend — porte aussi le compteur pending pour
/// l'UI (badge sur le bouton du menu Crédit).
@immutable
class AvalisteMandatList {
  const AvalisteMandatList({required this.items, required this.pendingCount});
  final List<AvalisteMandat> items;
  final int pendingCount;

  /// Voir `AvalisteMandat.toJson` — c'est cette empreinte que le poller
  /// compare pour décider s'il pousse une mise à jour.
  Map<String, dynamic> toJson() => {
        'pending_count': pendingCount,
        'items': items.map((m) => m.toJson()).toList(),
      };
}
