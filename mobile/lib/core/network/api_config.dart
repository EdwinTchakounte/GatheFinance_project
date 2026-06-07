/// Configuration réseau injectée à la compilation via `--dart-define`.
///
/// Valeurs par défaut visent le backend Docker local exposé sur 8200
/// (cf. docker-compose.yml) et l'émulateur Android qui voit l'hôte via
/// `10.0.2.2`. Sur device physique, surcharger :
///
///   flutter run --dart-define=API_BASE_URL=https://api.gathe-finance.horus-lab.com
///
/// Pour les tests / le build CI, on peut aussi forcer le mode mock :
///
///   flutter run --dart-define=USE_MOCKS=true
class ApiConfig {
  ApiConfig._();

  /// URL absolue du backend (sans slash final). En dev par défaut, on cible
  /// `10.0.2.2:8200` pour l'émulateur Android. Pour iOS sim ou web, passer
  /// explicitement `http://localhost:8200` via `--dart-define`.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8200',
  );

  /// Préfixe de l'API métier (chemin relatif à [baseUrl]).
  static const String apiPrefix = '/api/v1';

  /// URL complète préfixée (concaténation pratique).
  static String get apiBase => '$baseUrl$apiPrefix';

  /// Bascule globale "tout est mocké" — utilisée par le DI pour ne pas
  /// instancier la couche HTTP quand on développe sans backend.
  static const bool useMocks = bool.fromEnvironment(
    'USE_MOCKS',
    defaultValue: false,
  );

  /// Timeout réseau par défaut (connect + receive).
  static const Duration timeout = Duration(seconds: 25);
}
