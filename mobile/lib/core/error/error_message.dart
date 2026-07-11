import 'failures.dart';

/// Message d'erreur **présentable à l'utilisateur** — jamais de détail
/// technique (Dio, stacktrace, « Exception: … »).
///
/// - `Failure` → son message métier (déjà lisible).
/// - Exception brute → préfixe technique retiré ; si ça ressemble à du bruit
///   réseau/technique, on renvoie un message générique.
String friendlyError(
  Object? e, {
  String fallback = 'Une erreur est survenue. Réessaie.',
}) {
  if (e is Failure) return e.message;
  if (e == null) return fallback;
  final s = e.toString().replaceFirst('Exception: ', '').trim();
  if (s.isEmpty) return fallback;
  final lower = s.toLowerCase();
  if (lower.contains('dioexception') ||
      lower.contains('socketexception') ||
      lower.contains('connection') ||
      lower.contains('timeout') ||
      lower.contains('handshake') ||
      lower.startsWith('null')) {
    return 'Connexion impossible. Vérifie ta connexion et réessaie.';
  }
  return s;
}
