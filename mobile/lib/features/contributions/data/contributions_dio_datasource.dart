import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';
import '../../../core/network/api_exceptions.dart';
import '../domain/entities/contribution.dart';
import 'contributions_remote_datasource.dart';

/// Implémentation HTTP — `GET /api/v1/payments/me/`.
///
/// On agrège ici les frais visibles dans la page « Mes cotisations » :
/// adhésion, inscription, demande crédit, carnet, reconduction. On filtre
/// localement les remboursements / dépôts épargne, qui ont leurs propres
/// pages.
class ContributionsDioDataSource implements ContributionsRemoteDataSource {
  ContributionsDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  static const _shownTypes = <String>{
    'frais_adhesion',
    'frais_inscription',
    'frais_demande_credit',
    'frais_carnet',
    'frais_reconduction',
  };

  @override
  Future<List<Contribution>> fetchMine() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/payments/me/');
      final results = (res.data?['results'] as List<dynamic>?) ?? const [];
      return results
          .map((r) => _parse(r as Map<String, dynamic>))
          .where((c) => c != null)
          .cast<Contribution>()
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  static Contribution? _parse(Map<String, dynamic> json) {
    final rawType = (json['type'] as String?) ?? '';
    if (!_shownTypes.contains(rawType)) return null;
    return Contribution(
      id: (json['id'] as num).toInt(),
      type: _typeFromApi(rawType),
      montant: _num(json['montant']),
      statut: _statutFromApi((json['statut'] as String?) ?? 'en_attente'),
      date: _date(json['date_versement'] ?? json['created_at']),
      reference: (json['reference_externe'] as String?) ?? '',
    );
  }
}

ContributionType _typeFromApi(String raw) {
  switch (raw) {
    case 'frais_adhesion':
      return ContributionType.fraisAdhesion;
    case 'frais_inscription':
      return ContributionType.fraisInscription;
    case 'frais_demande_credit':
      return ContributionType.fraisDemandeCredit;
    case 'frais_reconduction':
      return ContributionType.fraisReconduction;
    case 'frais_carnet':
    default:
      return ContributionType.fraisCarnet;
  }
}

ContributionStatus _statutFromApi(String raw) {
  switch (raw) {
    case 'valide':
      return ContributionStatus.valide;
    case 'rejete':
    case 'annule':
      return ContributionStatus.echec;
    case 'en_attente':
    default:
      return ContributionStatus.enAttente;
  }
}

num _num(dynamic v) {
  if (v is num) return v;
  if (v is String) return num.tryParse(v) ?? 0;
  return 0;
}

DateTime _date(dynamic v) {
  if (v is String && v.isNotEmpty) {
    return DateTime.tryParse(v) ?? DateTime.now();
  }
  return DateTime.now();
}
