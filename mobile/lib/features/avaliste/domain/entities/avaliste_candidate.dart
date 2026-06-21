import 'package:flutter/foundation.dart';

/// Membre éligible à être avaliste — résultat d'un typeahead.
///
/// Renvoyé par `GET /api/v1/members/search-avaliste/`. Le solde n'est PAS
/// exposé (sera dans un autre lot — voir memory `avaliste-cap-solde`).
@immutable
class AvalisteCandidate {
  const AvalisteCandidate({
    required this.numeroMembre,
    required this.nom,
    required this.prenom,
    required this.isSenior,
    this.soldeTotal = 0,
    this.cautionsEngagees = 0,
    this.capaciteCaution = 0,
  });

  final String numeroMembre;
  final String nom;
  final String prenom;
  final bool isSenior;

  /// Note mémoire `avaliste-cap-solde` : trio exposé par le backend pour
  /// que le picker mobile affiche un hint et désactive un candidat sans
  /// capacité restante.
  final num soldeTotal;
  final num cautionsEngagees;
  final num capaciteCaution;

  String get displayName => '$prenom $nom · $numeroMembre';
}
