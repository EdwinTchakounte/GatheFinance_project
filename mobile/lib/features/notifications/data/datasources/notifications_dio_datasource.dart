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
}

AppNotification _parseNotification(Map<String, dynamic> json) {
  final type = (json['type'] as String?) ?? '';
  final message = (json['message'] as String?) ?? '';
  // Backend renvoie un seul `message` — on dérive title/body : le titre = type
  // formaté lisible, le body = le message complet.
  return AppNotification(
    id: (json['id'] as num).toInt(),
    kind: _kindFromType(type),
    title: _titleFromType(type),
    body: message,
    createdAt: _date(json['created_at']),
    read: (json['lue'] as bool?) ?? false,
  );
}

NotifKind _kindFromType(String type) {
  if (type.startsWith('savings') || type.startsWith('withdrawal')) {
    return NotifKind.savings;
  }
  if (type.startsWith('loan') || type.startsWith('repayment')) {
    return NotifKind.loan;
  }
  if (type.startsWith('payment')) return NotifKind.payment;
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
