import '../../domain/entities/avaliste_candidate.dart';
import '../../domain/entities/avaliste_mandat.dart';

/// Contrat de la datasource. Deux implémentations : mock + Dio.
abstract class AvalisteRemoteDataSource {
  Future<AvalisteMandatList> list({AvalisteStatut? statut});

  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
  });

  /// Typeahead — recherche d'avalistes éligibles (membres actifs+seniors)
  /// matchant `query` (préfixe numéro OU sous-chaîne nom). Renvoie liste vide
  /// si `query.length < 2`.
  Future<List<AvalisteCandidate>> searchEligible({required String query});
}
