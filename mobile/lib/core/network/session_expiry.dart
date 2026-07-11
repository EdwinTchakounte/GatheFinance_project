import 'dart:async';

/// Bus global « session expirée ».
///
/// Un intercepteur Dio ([SessionExpiryInterceptor]) le déclenche dès que le
/// backend répond 401 / 403-non-authentifié sur un endpoint métier. La racine
/// de l'app ([GatheApp]) écoute et rebascule vers l'écran de connexion (en
/// vidant la session + invalidant `authProvider`, ce qui fait rediriger le
/// router). Objectif : ne plus « marteler » l'API avec des requêtes 403 quand
/// la session a expiré — on route proprement vers le login.
class SessionExpiryBus {
  SessionExpiryBus._();
  static final SessionExpiryBus instance = SessionExpiryBus._();

  final StreamController<void> _controller = StreamController<void>.broadcast();
  Stream<void> get stream => _controller.stream;

  DateTime? _lastEmit;

  /// Émet un événement d'expiration — débounced : plusieurs pollers peuvent
  /// tomber en 403 quasi simultanément, on n'en propage qu'un par fenêtre.
  void notifyExpired() {
    final now = DateTime.now();
    final last = _lastEmit;
    if (last != null && now.difference(last) < const Duration(seconds: 5)) {
      return;
    }
    _lastEmit = now;
    if (!_controller.isClosed) _controller.add(null);
  }
}
