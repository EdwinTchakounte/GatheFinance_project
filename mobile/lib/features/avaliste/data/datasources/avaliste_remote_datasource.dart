import '../../domain/entities/avaliste_mandat.dart';

/// Contrat de la datasource. Deux implémentations : mock + Dio.
abstract class AvalisteRemoteDataSource {
  Future<AvalisteMandatList> list({AvalisteStatut? statut});

  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
  });
}
