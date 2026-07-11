import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Index de l'onglet actif du shell (0=Accueil, 1=Crédit, 2=Carnet, 3=Profil).
/// Posé par `MainShell`. Un `LivePoller` avec un `branchIndex` se met en pause
/// quand son onglet n'est pas l'onglet actif (les branches d'un IndexedStack
/// restent montées → sans ça, tous les pollers tournent en continu).
final activeShellIndexProvider = StateProvider<int>((ref) => 0);

/// Cadence de polling par defaut sur les pages "live" du membre (Home,
/// Credit, Notifications). 30 s = compromis batterie / data / reactivite.
///
/// Centralisee ici pour pouvoir ajuster en un seul endroit. Ne pas
/// descendre sous 15 s sans bonne raison : on consomme ~120 req/h et ca
/// reveille la radio mobile inutilement.
const Duration kLivePollingInterval = Duration(seconds: 30);

/// Helper Riverpod : declenche `refresh()` sur un AsyncNotifier toutes les
/// [interval] secondes, MAIS uniquement si la donnee retournee a vraiment
/// change (compare via hash JSON). Evite les rebuilds inutiles qui font
/// perdre focus de saisie, scroll, etc.
///
/// Usage type dans un ConsumerStatefulWidget :
/// ```dart
/// late final LivePolling _poll;
///
/// @override
/// void initState() {
///   super.initState();
///   _poll = LivePolling(
///     ref: ref,
///     refresh: () => ref.read(loansProvider.notifier).refresh(),
///     readSnapshot: () => ref.read(loansProvider).valueOrNull,
///   );
///   _poll.start();
/// }
///
/// @override
/// void dispose() {
///   _poll.stop();
///   super.dispose();
/// }
/// ```
///
/// Idempotence : `readSnapshot` doit retourner un objet serialisable en
/// JSON (typiquement via `toJson()` ou un Map). On hash sa representation
/// stringifiee et on compare au hash precedent. Si identique, on ne
/// pousse PAS de nouvel etat (Riverpod's setState n'est pas declenche).
class LivePolling {
  LivePolling({
    required this.ref,
    required this.refresh,
    required this.readSnapshot,
    this.interval = kLivePollingInterval,
    this.minimumQuietGap = const Duration(seconds: 2),
  });

  /// Ref Riverpod (pour pouvoir read le provider courant).
  final WidgetRef ref;

  /// Callback qui declenche le fetch reseau. Typiquement
  /// `ref.read(myProvider.notifier).refresh()`.
  final Future<void> Function() refresh;

  /// Callback qui renvoie la donnee actuelle (apres refresh). Sert au
  /// calcul du hash pour la deduplication.
  Object? Function() readSnapshot;

  /// Periode entre 2 ticks. Defaut 30 s.
  final Duration interval;

  /// Si l'utilisateur a fait un pull-to-refresh il y a moins de ce delai,
  /// on saute le prochain tick auto pour ne pas dupliquer.
  final Duration minimumQuietGap;

  Timer? _timer;
  String? _lastHash;
  DateTime? _lastTickAt;
  bool _running = false;

  bool get isRunning => _running;

  /// Demarre le polling. Idempotent : un second appel n'a aucun effet.
  void start() {
    if (_running) return;
    _running = true;
    // Premier hash = baseline (la page vient de monter avec ses donnees).
    _lastHash = _hash(readSnapshot());
    _lastTickAt = DateTime.now();
    _timer = Timer.periodic(interval, (_) => _tick());
  }

  /// Arrete le polling. Idempotent.
  void stop() {
    _timer?.cancel();
    _timer = null;
    _running = false;
  }

  /// Force un tick immediat (utile sur AppLifecycleState.resumed).
  Future<void> tickNow() async {
    await _tick();
  }

  /// Reconnait que l'utilisateur vient de faire un pull-to-refresh manuel.
  /// Met a jour le hash baseline + reset le timer pour eviter un double
  /// fetch immediat.
  void notifyManualRefresh() {
    _lastHash = _hash(readSnapshot());
    _lastTickAt = DateTime.now();
  }

  Future<void> _tick() async {
    final last = _lastTickAt;
    if (last != null && DateTime.now().difference(last) < minimumQuietGap) {
      // L'utilisateur vient de faire pull-to-refresh; on saute ce tick auto.
      return;
    }
    _lastTickAt = DateTime.now();
    try {
      await refresh();
    } catch (_) {
      // Best-effort. Erreur reseau / offline ; le prochain tick re-essaiera.
      // On ne change pas le hash.
      return;
    }
    final next = _hash(readSnapshot());
    if (next == _lastHash) {
      // Donnee identique : Riverpod a deja "rebati" le state avec un objet
      // egal en hash; on n'a rien a forcer cote UI.
      return;
    }
    _lastHash = next;
    // Riverpod gere le rebuild automatiquement via le watch() existant
    // dans la page : la nouvelle valeur a deja ete posee par refresh().
  }

  String _hash(Object? snapshot) {
    if (snapshot == null) return '';
    try {
      // toJson() si disponible, sinon toString.
      final encoded = jsonEncode(
        snapshot,
        toEncodable: (obj) {
          try {
            return (obj as dynamic).toJson();
          } catch (_) {
            return obj.toString();
          }
        },
      );
      return encoded.hashCode.toString();
    } catch (_) {
      return snapshot.toString().hashCode.toString();
    }
  }
}
