import 'package:flutter/foundation.dart';

/// Membre éligible à être avaliste — résultat d'un typeahead.
///
/// Renvoyé par `GET /api/v1/members/search-avaliste/`. SÉCURITÉ : seule la
/// capacité de caution restante est exposée — le solde total et les cautions
/// déjà engagées d'un autre membre ne sont plus divulgués au demandeur.
@immutable
class AvalisteCandidate {
  const AvalisteCandidate({
    required this.numeroMembre,
    required this.nom,
    required this.prenom,
    required this.isSenior,
    this.capaciteCaution = 0,
  });

  final String numeroMembre;
  final String nom;
  final String prenom;
  final bool isSenior;

  /// Capacité de caution restante (épargne classique disponible du candidat).
  /// Sert au picker à afficher « peut garantir jusqu'à X » et à désactiver un
  /// candidat saturé (capacité ≤ 0).
  final num capaciteCaution;

  String get displayName => '$prenom $nom · $numeroMembre';
}
