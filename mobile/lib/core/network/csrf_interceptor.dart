import 'package:cookie_jar/cookie_jar.dart';
import 'package:dio/dio.dart';

import 'api_config.dart';

/// Injecte `X-CSRFToken` sur toutes les requêtes mutantes (POST/PATCH/DELETE)
/// en relisant le cookie `csrftoken` posé par le backend.
///
/// Django CSRF middleware exige aussi que l'origine corresponde — pour les
/// requêtes API depuis le mobile c'est OK tant que `CSRF_TRUSTED_ORIGINS`
/// inclut l'origine du mobile (ce qui n'est pas le cas par défaut). On
/// désactive donc côté backend la vérification d'origine via le décorateur
/// `csrf_exempt` sur l'endpoint login, OU on s'aligne sur les origines
/// trust-list (préféré). En attendant, le simple envoi du token suffit
/// dans la plupart des cas (DRF SessionAuthentication).
class CsrfInterceptor extends Interceptor {
  CsrfInterceptor(this._cookieJar);

  final CookieJar _cookieJar;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final method = options.method.toUpperCase();
    if (method == 'GET' || method == 'HEAD' || method == 'OPTIONS') {
      handler.next(options);
      return;
    }
    // Django CSRF middleware en HTTPS rejette toute requête POST sans Referer
    // valide ("Referer checking failed — no Referer"). On force Origin + Referer
    // à pointer sur l'API elle-même, qui est dans CSRF_TRUSTED_ORIGINS.
    options.headers['Origin'] = ApiConfig.baseUrl;
    options.headers['Referer'] = '${ApiConfig.baseUrl}/';
    try {
      final uri = Uri.parse(ApiConfig.baseUrl);
      final cookies = await _cookieJar.loadForRequest(uri);
      for (final c in cookies) {
        if (c.name == 'csrftoken' && c.value.isNotEmpty) {
          options.headers['X-CSRFToken'] = c.value;
          break;
        }
      }
    } catch (_) {
      // best-effort — pas de cookie = on continue, le backend renverra 403.
    }
    handler.next(options);
  }
}
