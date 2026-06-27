import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/lender_state.dart';

/// LOT 19 — Source distante pour l'espace prêteur du membre.
///
/// Routes (toutes sous `/api/v1/`) :
///   - GET  /savings/me/lender/                                   → [me]
///   - POST /savings/me/lender/opt-in/      { is_global: bool }   → [optIn]
///   - POST /savings/me/lender/revoke/                            → [revoke]
///   - POST /savings/me/lender/tranches/    { montant }           → [addTranche]
///   - POST /savings/me/lender/tranches/`<id>`/cancel/              → [cancelTranche]
///   - POST /savings/me/lender/funding-requests/`<id>`/respond/
///                                          { accept: bool, comment? } → [respondFunding]
class LenderDioDataSource {
  LenderDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  Future<LenderState> me() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/savings/me/lender/');
      return _parseState(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<LenderState> optIn({required bool isGlobal}) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/savings/me/lender/opt-in/',
        data: {'is_global': isGlobal},
      );
      return _parseState(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<LenderState> revoke() async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/savings/me/lender/revoke/',
      );
      return _parseState(res.data ?? const {});
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> addTranche({required num montant}) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/savings/me/lender/tranches/',
        data: {'montant': montant.toString()},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> cancelTranche({required int trancheId}) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/savings/me/lender/tranches/$trancheId/cancel/',
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  Future<void> respondFunding({
    required int consentRequestId,
    required bool accept,
    String? comment,
  }) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/savings/me/lender/funding-requests/$consentRequestId/respond/',
        data: {
          'accept': accept,
          if (comment != null && comment.isNotEmpty) 'comment': comment,
        },
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  // -- parsing -------------------------------------------------------------

  LenderState _parseState(Map<String, dynamic> json) {
    return LenderState(
      consent: _parseConsent(json['consent'] as Map<String, dynamic>?),
      tranches: ((json['tranches'] as List?) ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(_parseTranche)
          .toList(growable: false),
      totals: _parseTotals(json['totals'] as Map<String, dynamic>?),
      pendingFundingRequests:
          ((json['pending_funding_requests'] as List?) ?? const [])
              .whereType<Map<String, dynamic>>()
              .map(_parseFunding)
              .toList(growable: false),
    );
  }

  LenderConsent? _parseConsent(Map<String, dynamic>? json) {
    if (json == null || json.isEmpty) return null;
    final signedRaw = json['signed_at'] as String?;
    if (signedRaw == null || signedRaw.isEmpty) return null;
    return LenderConsent(
      isGlobal: (json['is_global'] as bool?) ?? true,
      signedAt: DateTime.tryParse(signedRaw) ?? DateTime.now(),
      revokedAt: _date(json['revoked_at']),
    );
  }

  LenderTranche _parseTranche(Map<String, dynamic> json) {
    return LenderTranche(
      id: (json['id'] as num?)?.toInt() ?? 0,
      montant: num.tryParse('${json['montant']}') ?? 0,
      statut: _trancheStatut((json['statut'] as String?) ?? 'disponible'),
      createdAt: _date(json['created_at']) ?? DateTime.now(),
      loanId: (json['loan_id'] as num?)?.toInt(),
    );
  }

  LenderTrancheStatut _trancheStatut(String raw) => switch (raw) {
        'engagee' => LenderTrancheStatut.engagee,
        'liberee' => LenderTrancheStatut.liberee,
        'annulee' => LenderTrancheStatut.annulee,
        _ => LenderTrancheStatut.disponible,
      };

  LenderTotals _parseTotals(Map<String, dynamic>? json) {
    json ??= const {};
    num parse(String key) => num.tryParse('${json![key] ?? 0}') ?? 0;
    return LenderTotals(
      disponible: parse('disponible'),
      engagee: parse('engagee'),
      liberee: parse('liberee'),
      annulee: parse('annulee'),
    );
  }

  FundingPending _parseFunding(Map<String, dynamic> json) {
    return FundingPending(
      consentRequestId: (json['id'] as num?)?.toInt() ?? 0,
      loanId: (json['loan_id'] as num?)?.toInt() ?? 0,
      memberName: (json['borrower_name'] as String?) ?? '',
      montant: num.tryParse('${json['montant']}') ?? 0,
      deadline: _date(json['deadline']) ?? DateTime.now(),
    );
  }

  DateTime? _date(dynamic raw) {
    if (raw is String && raw.isNotEmpty) return DateTime.tryParse(raw);
    return null;
  }
}
