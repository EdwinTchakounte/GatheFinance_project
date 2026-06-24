import 'package:flutter/foundation.dart';

/// Configuration réseau.
///
/// Priorité de résolution de [baseUrl] :
///   1. `--dart-define=API_BASE_URL=...` (surcharge explicite, gagne toujours)
///   2. En build RELEASE → `https://api.gathe-finance.horus-lab.com` (prod VPS)
///   3. En build DEBUG/PROFILE → `http://10.0.2.2:8200` (émulateur Android local)
///
/// Ce fallback release évite le bug "Failed host lookup" quand l'AAB est
/// publiée sans `--dart-define` : un device physique ne sait pas résoudre
/// `10.0.2.2` (IP virtuelle de l'émulateur Android seulement).
class ApiConfig {
  ApiConfig._();

  static const String _envOverride = String.fromEnvironment('API_BASE_URL');
  static const String _prodDefault = 'https://api.gathe-finance.horus-lab.com';
  static const String _devDefault = 'http://10.0.2.2:8200';

  /// URL absolue du backend (sans slash final).
  static String get baseUrl {
    if (_envOverride.isNotEmpty) return _envOverride;
    return kReleaseMode ? _prodDefault : _devDefault;
  }

  /// Préfixe de l'API métier (chemin relatif à [baseUrl]).
  static const String apiPrefix = '/api/v1';

  /// URL complète préfixée (concaténation pratique).
  static String get apiBase => '$baseUrl$apiPrefix';

  /// Timeout réseau par défaut (connect + receive).
  static const Duration timeout = Duration(seconds: 25);
}
