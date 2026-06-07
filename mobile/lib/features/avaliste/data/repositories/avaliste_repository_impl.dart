import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/avaliste_mandat.dart';
import '../../domain/repositories/avaliste_repository.dart';
import '../datasources/avaliste_remote_datasource.dart';

/// Traduit les exceptions techniques (data) en `Failure` métier.
class AvalisteRepositoryImpl implements AvalisteRepository {
  const AvalisteRepositoryImpl(this._remote);
  final AvalisteRemoteDataSource _remote;

  @override
  Future<AvalisteMandatList> list({AvalisteStatut? statut}) async {
    try {
      return await _remote.list(statut: statut);
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
  }) async {
    try {
      return await _remote.respond(
        mandatId: mandatId,
        accept: accept,
        motif: motif,
      );
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw BusinessFailure(e.message);
    }
  }
}
