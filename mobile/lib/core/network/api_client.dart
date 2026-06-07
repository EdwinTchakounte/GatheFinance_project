import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';
import 'package:dio_cookie_manager/dio_cookie_manager.dart';
import 'package:flutter/foundation.dart' show visibleForTesting;
import 'package:path_provider/path_provider.dart';

import 'api_config.dart';
import 'csrf_interceptor.dart';

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
    ]);

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
