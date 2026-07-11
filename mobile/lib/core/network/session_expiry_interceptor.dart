import 'package:dio/dio.dart';

import 'session_expiry.dart';

/// Détecte une session expirée (401 / 403-non-authentifié) et prévient le
/// [SessionExpiryBus] → la racine de l'app route vers le login au lieu de
/// laisser les pollers marteler l'API en boucle.
///
/// N'agit PAS sur :
///  - les endpoints `/auth/*` (login, `/auth/me/`, csrf) : ils gèrent leurs
///    propres 401/403 et invalider `authProvider` re-tape `/auth/me/` → boucle ;
///  - les 403 CSRF (détail contient « csrf ») : gérés/retentés ailleurs ;
///  - les 403 de permission (détail « permission » / « ressource non
///    autorisée ») : ce n'est pas une expiration de session.
class SessionExpiryInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (_isSessionExpired(err)) {
      SessionExpiryBus.instance.notifyExpired();
    }
    handler.next(err);
  }

  bool _isSessionExpired(DioException err) {
    if (err.requestOptions.path.contains('/auth/')) return false;
    final code = err.response?.statusCode;
    if (code == 401) return true;
    if (code != 403) return false;
    final data = err.response?.data;
    final detail =
        (data is Map ? (data['detail']?.toString() ?? '') : '').toLowerCase();
    // DRF NotAuthenticated : « Authentication credentials were not provided. »
    // / « Informations d'authentification non fournies. »
    return detail.contains('not provided') ||
        detail.contains('non fournies') ||
        detail.contains('authentication credentials') ||
        detail.contains("informations d'authentification");
  }
}
