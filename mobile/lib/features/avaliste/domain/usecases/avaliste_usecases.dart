import 'package:flutter/foundation.dart';

import '../../../../core/usecases/usecase.dart';
import '../entities/avaliste_mandat.dart';
import '../repositories/avaliste_repository.dart';

@immutable
class ListAvalisteParams {
  const ListAvalisteParams({this.statut});
  final AvalisteStatut? statut;
}

class ListAvalisteMandats
    extends UseCase<AvalisteMandatList, ListAvalisteParams> {
  const ListAvalisteMandats(this._repo);
  final AvalisteRepository _repo;

  @override
  Future<AvalisteMandatList> call(ListAvalisteParams params) {
    return _repo.list(statut: params.statut);
  }
}

@immutable
class RespondAvalisteParams {
  const RespondAvalisteParams({
    required this.mandatId,
    required this.accept,
    this.motif,
    this.cniAvaliste,
    this.cniFichierPath,
    this.cniFichierName,
  });
  final int mandatId;
  final bool accept;
  final String? motif;
  // L5 identité . renseignés uniquement à l'acceptation.
  final String? cniAvaliste;
  final String? cniFichierPath;
  final String? cniFichierName;
}

class RespondAvalisteMandat
    extends UseCase<AvalisteMandat, RespondAvalisteParams> {
  const RespondAvalisteMandat(this._repo);
  final AvalisteRepository _repo;

  @override
  Future<AvalisteMandat> call(RespondAvalisteParams params) {
    return _repo.respond(
      mandatId: params.mandatId,
      accept: params.accept,
      motif: params.motif,
      cniAvaliste: params.cniAvaliste,
      cniFichierPath: params.cniFichierPath,
      cniFichierName: params.cniFichierName,
    );
  }
}
