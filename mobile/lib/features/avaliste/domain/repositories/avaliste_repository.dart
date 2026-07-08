import '../entities/avaliste_mandat.dart';

/// Contrat de la couche data pour les mandats d'avaliste — implémenté
/// dans `data/repositories/avaliste_repository_impl.dart`.
abstract class AvalisteRepository {
  /// Liste les mandats où le membre connecté est désigné comme garant.
  /// Filtre optionnel par statut.
  Future<AvalisteMandatList> list({AvalisteStatut? statut});

  /// Répond à un mandat : accepte ou refuse (avec motif).
  /// À l'acceptation (L5 identité), le numéro de CNI de l'avaliste + son
  /// justificatif sont requis. Renvoie le mandat à jour.
  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
    String? cniAvaliste,
    String? cniFichierPath,
    String? cniFichierName,
  });
}
