import 'dart:io' show SocketException;

import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart' show debugPrint, kDebugMode, visibleForTesting;
import 'package:path_provider/path_provider.dart';

import 'api_config.dart';
import 'csrf_interceptor.dart';
import 'session_expiry_interceptor.dart';

/// Client HTTP unique de l'app — Dio + persistance cookies (sessionid +
/// csrftoken) sur disque via `PersistCookieJar`. La session survit aux
/// redémarrages de l'app tant que `signOut()` n'est pas appelé.
class ApiClient {
  ApiClient._(this.dio, this.cookieJar);

  /// Factory de test — accepte un `Dio` déjà câblé (souvent avec un
  /// `ScriptedAdapter`) et un `CookieJar` en mémoire. Pas d'I/O disque.
  @visibleForTesting
  factory ApiClient.forTest({required Dio dio, CookieJar? cookieJar}) {
    return ApiClient._(dio, cookieJar ?? CookieJar());
  }

  final Dio dio;
  final CookieJar cookieJar;

  /// Factory async — récupère le dossier de support pour stocker les cookies.
  /// Doit être appelé une seule fois au démarrage (cf. `core/di/providers.dart`).
  static Future<ApiClient> create() async {
    final dir = await getApplicationSupportDirectory();
    final jar = PersistCookieJar(
      ignoreExpires: false,
      storage: FileStorage('${dir.path}/.cookies'),
    );

    final dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.apiBase,
        connectTimeout: ApiConfig.timeout,
        receiveTimeout: ApiConfig.timeout,
        sendTimeout: ApiConfig.timeout,
        contentType: 'application/json',
        responseType: ResponseType.json,
        // Backend renvoie 400/401/403/422 avec un body JSON exploitable —
        // on laisse Dio remonter ces erreurs, mappées ensuite par
        // `mapDioError` dans les datasources.
        validateStatus: (s) => s != null && s >= 200 && s < 400,
        headers: const {
          'Accept': 'application/json',
        },
      ),
    );

    dio.interceptors.addAll([
      CookieManager(jar),
      CsrfInterceptor(jar),
      _RetryInterceptor(dio),
      // En dernier : observe l'erreur finale (après retry réseau) pour
      // détecter une session expirée → route vers le login (plus de martèlement).
      SessionExpiryInterceptor(),
    ]);

    if (kDebugMode) {
      dio.interceptors.add(
        LogInterceptor(
          requestHeader: false,
          requestBody: true,
          responseHeader: false,
          responseBody: true,
          error: true,
          logPrint: (o) => debugPrint('[DIO] $o'),
        ),
      );
    }

    return ApiClient._(dio, jar);
  }

  /// Vide les cookies (sessionid + csrftoken) — appelé sur signOut pour
  /// repartir d'une session vierge.
  Future<void> clearSession() async {
    await cookieJar.deleteAll();
  }

  /// Amorce le cookie `csrftoken` via `GET /auth/csrf/`. À appeler avant
  /// toute requête mutante anonyme (typiquement le premier login).
  Future<void> primeCsrf() async {
    await dio.get<void>('/auth/csrf/');
  }
}

/// Retry sur erreurs DNS/connexion (jusqu'à 3 tentatives, backoff progressif).
///
/// Sur Android, le premier appel HTTPS échoue parfois avec
/// `SocketException: Failed host lookup` car le résolveur DNS de Dart n'a pas
/// encore chauffé. Un simple retry après 400 ms suffit dans la quasi-totalité
/// des cas.
class _RetryInterceptor extends Interceptor {
  _RetryInterceptor(this._dio);

  final Dio _dio;
  static const int _maxAttempts = 3;

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (!_isRetryable(err)) {
      handler.next(err);
      return;
    }
    final attempts = (err.requestOptions.extra['_retryAttempt'] as int?) ?? 0;
    if (attempts >= _maxAttempts) {
      handler.next(err);
      return;
    }
    final delay = Duration(milliseconds: 300 * (attempts + 1));
    debugPrint(
      '[RETRY] ${err.requestOptions.method} ${err.requestOptions.uri} '
      'failed (${err.type}) — attempt ${attempts + 1}/$_maxAttempts after '
      '${delay.inMilliseconds}ms',
    );
    await Future<void>.delayed(delay);
    final newOptions = err.requestOptions;
    newOptions.extra['_retryAttempt'] = attempts + 1;
    try {
      final response = await _dio.fetch<dynamic>(newOptions);
      handler.resolve(response);
    } on DioException catch (e) {
      handler.next(e);
    } catch (_) {
      handler.next(err);
    }
  }

  bool _isRetryable(DioException err) {
    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.connectionError) {
      return true;
    }
    if (err.error is SocketException) return true;
    final msg = err.message ?? '';
    if (msg.toLowerCase().contains('failed host lookup')) return true;
    return false;
  }
}
