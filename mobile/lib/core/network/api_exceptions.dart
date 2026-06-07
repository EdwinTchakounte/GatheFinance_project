import 'package:dio/dio.dart';

import '../error/exceptions.dart';

/// Traduit une `DioException` en exception métier interne (`ServerException` /
/// `NetworkException` / `CredentialsException`). Les repository impls
/// transformeront ensuite en `Failure` côté domain — la chaîne reste
/// `data → domain` propre.
Object mapDioError(DioException e) {
  // Timeout / DNS / no internet → NetworkException
  switch (e.type) {
    case DioExceptionType.connectionTimeout:
    case DioExceptionType.sendTimeout:
    case DioExceptionType.receiveTimeout:
    case DioExceptionType.connectionError:
      return NetworkException(e.message ?? 'Connexion impossible.');
    case DioExceptionType.badCertificate:
      return const NetworkException('Certificat HTTPS invalide.');
    case DioExceptionType.cancel:
      return const NetworkException('Requête annulée.');
    case DioExceptionType.unknown:
      // unknown sans response = panne réseau probable
      if (e.response == null) {
        return NetworkException(e.message ?? 'Connexion impossible.');
      }
      break;
    case DioExceptionType.badResponse:
      break;
  }

  final response = e.response;
  if (response == null) {
    return ServerException(e.message ?? 'Erreur réseau', null);
  }
  final status = response.statusCode ?? 0;
  final detail = _extractDetail(response.data);

  if (status == 401 || status == 403) {
    return CredentialsException(
      detail ?? (status == 401 ? 'Session expirée.' : 'Accès refusé.'),
    );
  }
  return ServerException(detail ?? 'Erreur serveur', status);
}

String? _extractDetail(dynamic body) {
  if (body is Map<String, dynamic>) {
    final detail = body['detail'];
    if (detail is String && detail.isNotEmpty) return detail;
    // DRF renvoie souvent { "field": ["message"] } pour les erreurs de validation.
    for (final value in body.values) {
      if (value is List && value.isNotEmpty && value.first is String) {
        return value.first as String;
      }
      if (value is String && value.isNotEmpty) return value;
    }
  }
  if (body is String && body.isNotEmpty) return body;
  return null;
}
