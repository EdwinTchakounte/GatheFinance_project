import 'package:flutter/foundation.dart';

/// Résultat de l'évaluation d'éligibilité à un nouveau crédit (UC3 step 0).
///
/// `motifs` est non vide quand `eligible == false` : ce sont les raisons
/// communiquées au membre dans l'UI (ex. « Un crédit est déjà en cours »).
@immutable
class Eligibility {
  const Eligibility({
    required this.eligible,
    required this.plafondMax,
    required this.soldeEpargne,
    required this.ratioGarantie,
    required this.motifs,
  });

  final bool eligible;
  final num plafondMax;
  final num soldeEpargne;
  final num ratioGarantie;
  final List<String> motifs;
}
