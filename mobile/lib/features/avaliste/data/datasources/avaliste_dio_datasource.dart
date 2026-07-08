import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/avaliste_candidate.dart';
import '../../domain/entities/avaliste_mandat.dart';
import 'avaliste_remote_datasource.dart';

/// Implémentation HTTP de [AvalisteRemoteDataSource].
///
///   - GET  /loans/me/avaliste-mandats/?statut=pending|accepted|refused
///   - POST /loans/me/avaliste-mandats/{id}/respond/ {accept, motif?}
class AvalisteDioDataSource implements AvalisteRemoteDataSource {
  AvalisteDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<AvalisteMandatList> list({AvalisteStatut? statut}) async {
    try {
      final query = <String, dynamic>{};
      if (statut != null) query['statut'] = _statutToApi(statut);
      final res = await _dio.get<Map<String, dynamic>>(
        '/loans/me/avaliste-mandats/',
        queryParameters: query.isEmpty ? null : query,
      );
      final data = res.data ?? const {};
      final raw = (data['results'] as List<dynamic>?) ?? const [];
      return AvalisteMandatList(
        items: raw
            .map((m) => _parseMandat(m as Map<String, dynamic>))
            .toList(growable: false),
        pendingCount: (data['pending'] as num?)?.toInt() ?? 0,
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<AvalisteMandat> respond({
    required int mandatId,
    required bool accept,
    String? motif,
    String? cniAvaliste,
    String? cniFichierPath,
    String? cniFichierName,
  }) async {
    try {
      final Object data;
      if (accept) {
        // L5 identité . L'acceptation exige le numéro de CNI de l'avaliste + une
        // pièce jointe (photo/scan). Le backend renvoie 400 sinon. Requête
        // multipart pour transporter le fichier avec les scalaires.
        data = FormData.fromMap({
          'accept': 'true',
          if (cniAvaliste != null) 'cni_avaliste': cniAvaliste.trim(),
          if (cniFichierPath != null)
            'cni_avaliste_fichier': await MultipartFile.fromFile(
              cniFichierPath,
              filename: cniFichierName,
            ),
        });
      } else {
        // Refus . inchangé : JSON {accept:false, motif?}.
        final body = <String, dynamic>{'accept': false};
        if (motif != null && motif.trim().isNotEmpty) {
          body['motif'] = motif.trim();
        }
        data = body;
      }
      final res = await _dio.post<Map<String, dynamic>>(
        '/loans/me/avaliste-mandats/$mandatId/respond/',
        data: data,
      );
      return _parseMandat(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<List<AvalisteCandidate>> searchEligible({required String query}) async {
    if (query.trim().length < 2) return const [];
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/members/search-avaliste/',
        queryParameters: {'q': query.trim()},
      );
      final raw = (res.data?['results'] as List<dynamic>?) ?? const [];
      return raw
          .map((e) => _parseCandidate(e as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

AvalisteCandidate _parseCandidate(Map<String, dynamic> json) {
  return AvalisteCandidate(
    numeroMembre: (json['numero_membre'] as String?) ?? '',
    nom: (json['nom'] as String?) ?? '',
    prenom: (json['prenom'] as String?) ?? '',
    isSenior: (json['is_senior'] as bool?) ?? true,
    soldeTotal: num.tryParse('${json['solde_total']}') ?? 0,
    cautionsEngagees: num.tryParse('${json['cautions_engagees']}') ?? 0,
    capaciteCaution: num.tryParse('${json['capacite_caution']}') ?? 0,
  );
}

AvalisteMandat _parseMandat(Map<String, dynamic> json) {
  final demandeur = json['demandeur'] as Map<String, dynamic>? ?? const {};
  final loan = json['loan_request'] as Map<String, dynamic>? ?? const {};
  final couv = json['couverture'] as Map<String, dynamic>? ?? const {};
  return AvalisteMandat(
    id: (json['id'] as num).toInt(),
    statut: _statutFromApi((json['statut'] as String?) ?? 'pending'),
    statutDisplay: (json['statut_display'] as String?) ?? '',
    respondedAt: json['responded_at'] != null ? _date(json['responded_at']) : null,
    refusMotif: (json['refus_motif'] as String?) ?? '',
    createdAt: _date(json['created_at']),
    demandeur: AvalisteDemandeur(
      id: (demandeur['id'] as num?)?.toInt() ?? 0,
      numeroMembre: (demandeur['numero_membre'] as String?) ?? '',
      prenom: (demandeur['prenom'] as String?) ?? '',
      nom: (demandeur['nom'] as String?) ?? '',
    ),
    loanRequest: AvalisteLoanRequest(
      id: (loan['id'] as num?)?.toInt() ?? 0,
      montantDemande: _num(loan['montant_demande']),
      dureeMois: (loan['duree_mois'] as num?)?.toInt() ?? 0,
      motif: (loan['motif'] as String?) ?? '',
      statut: (loan['statut'] as String?) ?? '',
      dateSoumission: _date(loan['date_soumission']),
    ),
    couverture: AvalisteCouverture(
      epargneBorrower: _num(couv['epargne_borrower']),
      epargneAvaliste: _num(couv['epargne_avaliste']),
      ratio: _num(couv['ratio']),
    ),
    montantGele: _num(json['montant_gele']),
    cniDemandeur: (json['cni_demandeur'] as String?) ?? '',
    cniAvaliste: (json['cni_avaliste'] as String?) ?? '',
    cniAvalisteFichier: (json['cni_avaliste_fichier'] as String?) ?? '',
  );
}

AvalisteStatut _statutFromApi(String raw) {
  switch (raw) {
    case 'accepted':
      return AvalisteStatut.accepted;
    case 'refused':
      return AvalisteStatut.refused;
    case 'pending':
    default:
      return AvalisteStatut.pending;
  }
}

String _statutToApi(AvalisteStatut s) {
  switch (s) {
    case AvalisteStatut.accepted:
      return 'accepted';
    case AvalisteStatut.refused:
      return 'refused';
    case AvalisteStatut.pending:
      return 'pending';
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
