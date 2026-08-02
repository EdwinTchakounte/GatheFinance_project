import 'failures.dart';

/// Message d'erreur **présentable à l'utilisateur** — jamais de détail
/// technique (Dio, stacktrace, « Exception: … »). Les problèmes de connexion
/// sont distingués (hors-ligne vs lenteur/serveur) pour rassurer l'utilisateur.

const _kOffline = 'Pas de connexion internet. Vérifie ton réseau et réessaie.';
const _kTimeout =
    'La connexion est lente ou le serveur tarde à répondre. Réessaie dans un '
    'instant.';
const _kServer =
    'Nos serveurs rencontrent un souci. Réessaie dans quelques instants.';

// Signaux HORS-LIGNE **précis** uniquement. On NE matche PAS « dioexception »
// ni « connection » seuls : une réponse serveur (400/403/500) est aussi une
// DioException et contient ces mots → sinon on afficherait « Pas de connexion »
// alors que le serveur a bien répondu. Un vrai hors-ligne se reconnaît à l'échec
// socket/DNS, pas à la présence d'une réponse HTTP.
bool _looksOffline(String lower) =>
    lower.contains('socketexception') ||
    lower.contains('failed host lookup') ||
    lower.contains('network is unreachable') ||
    lower.contains('no address associated with hostname') ||
    lower.contains('connection refused') ||
    lower.contains('connection reset') ||
    lower.contains('connection closed') ||
    lower.contains('connection timed out') ||
    lower.contains('handshake');

String friendlyError(
  Object? e, {
  String fallback = 'Une erreur est survenue. Réessaie.',
}) {
  // Réseau : on soigne le message selon hors-ligne vs lenteur.
  if (e is NetworkFailure) {
    final lower = e.message.toLowerCase();
    if (lower.contains('timeout') || lower.contains('lente')) return _kTimeout;
    if (lower.contains('certificat')) return e.message;
    // Message générique par défaut → on renvoie le libellé hors-ligne soigné.
    return e.message == 'Connexion impossible.' ? _kOffline : e.message;
  }
  if (e is Failure) return e.message; // déjà lisible (métier)
  if (e == null) return fallback;

  final s = e.toString().replaceFirst('Exception: ', '').trim();
  if (s.isEmpty) return fallback;
  final lower = s.toLowerCase();
  if (lower.contains('timeout')) return _kTimeout;
  if (_looksOffline(lower)) return _kOffline;
  if (lower.contains('http 5') ||
      lower.contains(' 500') ||
      lower.contains('server')) {
    return _kServer;
  }
  // Reste technique (« exception », très long…) → message générique.
  if (lower.contains('exception') || s.length > 140) return fallback;
  return s;
}

/// Vrai si l'erreur est un problème de connectivité (réseau/timeout) — sert à
/// afficher une variante « Pas de connexion » dans les états d'erreur.
bool isConnectivityError(Object? e) {
  if (e is NetworkFailure) return true;
  final lower = e?.toString().toLowerCase() ?? '';
  return lower.contains('timeout') || _looksOffline(lower);
}
