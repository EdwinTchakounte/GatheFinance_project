import 'package:dio/dio.dart';

import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_exceptions.dart';
import '../../domain/entities/app_notification.dart';
import 'notifications_remote_datasource.dart';

/// Implémentation HTTP de [NotificationsRemoteDataSource].
///
///   - GET  /notifications/         → `{results: [...], unread_count: n}`
///   - POST /notifications/{id}/read/
///   - POST /notifications/read-all/
class NotificationsDioDataSource implements NotificationsRemoteDataSource {
  NotificationsDioDataSource(this._client);

  final ApiClient _client;
  Dio get _dio => _client.dio;

  @override
  Future<List<AppNotification>> list() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/notifications/');
      final results = (res.data?['results'] as List<dynamic>?) ?? const [];
      return results
          .map((n) => _parseNotification(n as Map<String, dynamic>))
          .toList(growable: false);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> markAllRead() async {
    try {
      await _dio.post<void>('/notifications/read-all/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> markRead(int id) async {
    try {
      await _dio.post<void>('/notifications/$id/read/');
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> registerDevice(String token, {String platform = 'android'}) async {
    try {
      await _dio.post<void>(
        '/notifications/devices/register/',
        data: {'token': token, 'platform': platform},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<void> unregisterDevice(String token) async {
    try {
      await _dio.post<void>(
        '/notifications/devices/unregister/',
        data: {'token': token},
      );
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Map<String, bool>> getPushPrefs() async {
    try {
      final res =
          await _dio.get<Map<String, dynamic>>('/notifications/preferences/');
      return _parsePush(res.data);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }

  @override
  Future<Map<String, bool>> setPushPrefs(Map<String, bool> updates) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/notifications/preferences/',
        data: {'push': updates},
      );
      return _parsePush(res.data);
    } on DioException catch (e) {
      throw mapDioError(e);
    }
  }
}

Map<String, bool> _parsePush(Map<String, dynamic>? data) {
  final push = data?['push'];
  if (push is Map) {
    return {
      for (final entry in push.entries)
        entry.key.toString(): entry.value == true,
    };
  }
  return const {};
}

AppNotification _parseNotification(Map<String, dynamic> json) {
  final type = (json['type'] as String?) ?? '';
  final message = (json['message'] as String?) ?? '';
  // Backend renvoie un seul `message` — on dérive title/body :
  //   - cas général : titre = type formaté lisible, body = message complet ;
  //   - cas `type=="annonce"` : le backend prefixe le corps par le titre
  //     saisi par l'admin (broadcast), au format "TITRE\n\nCORPS" — on extrait
  //     proprement les 2 parties pour les afficher en hiérarchie naturelle.
  String title;
  String body;
  if (type == 'annonce') {
    final split = message.split(RegExp(r'\n\n+'));
    if (split.length >= 2 && split.first.trim().isNotEmpty) {
      title = split.first.trim();
      body = split.sublist(1).join('\n\n').trim();
    } else {
      title = 'Annonce';
      body = message;
    }
  } else {
    title = _titleFromType(type);
    body = message;
  }

  return AppNotification(
    id: (json['id'] as num).toInt(),
    kind: _kindFromType(type),
    title: title,
    body: body,
    createdAt: _date(json['created_at']),
    read: (json['lue'] as bool?) ?? false,
  );
}

NotifKind _kindFromType(String type) {
  if (type == 'annonce' || type.startsWith('annonce.')) {
    return NotifKind.announcement;
  }
  // lender.* couvre tranche engagee / interets percus / etc.
  if (type.startsWith('lender')) {
    return NotifKind.lender;
  }
  if (type.startsWith('savings') || type.startsWith('withdrawal')) {
    return NotifKind.savings;
  }
  // Sollicitation de garantie envoyée à l'AVALISTE désigné → doit ouvrir la
  // page « Mes mandats », pas la page crédit du demandeur. Les autres
  // `loan.avaliste_*` (accepté/refusé) partent au demandeur → restent `loan`.
  if (type == 'loan.avaliste_consent_requested') {
    return NotifKind.avaliste;
  }
  if (type.startsWith('loan') || type.startsWith('repayment')) {
    return NotifKind.loan;
  }
  if (type.startsWith('payment')) return NotifKind.payment;
  if (type.startsWith('support')) return NotifKind.support;
  return NotifKind.system;
}

String _titleFromType(String type) {
  if (type.isEmpty) return 'Notification';
  // Rend "payment.confirmed" → "Paiement confirmé" (best-effort lisible).
  final parts = type.split(RegExp(r'[._]'));
  final localized = parts
      .map((p) => p.isEmpty ? p : p[0].toUpperCase() + p.substring(1))
      .join(' ');
  return localized;
}

DateTime _date(dynamic value) {
  if (value is String && value.isNotEmpty) {
    return DateTime.tryParse(value) ?? DateTime.now();
  }
  return DateTime.now();
}
