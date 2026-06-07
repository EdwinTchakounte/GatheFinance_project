import '../domain/entities/contribution.dart';

/// Contrat de la datasource. Deux implémentations : mock + Dio.
abstract class ContributionsRemoteDataSource {
  Future<List<Contribution>> fetchMine();
}
