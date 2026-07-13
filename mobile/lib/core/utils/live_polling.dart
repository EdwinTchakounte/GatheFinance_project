import 'dart:async';

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
/// [interval] secondes, en mettant le timer en pause quand la page n'est pas
/// visible (cf. [LivePoller]).
///
/// La **deduplication** (ne rebuild que si la donnee a change) n'est PLUS
/// faite ici : elle vit desormais dans les notifiers via le mixin
/// `PollableAsyncNotifier.silentRefresh` — leur `refresh()` ne repousse un
/// nouvel etat que si le contenu differe et ne jette jamais la donnee
/// affichee. Ce helper se contente donc de cadencer les appels.
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
class LivePolling {
  LivePolling({
    required this.ref,
    required this.refresh,
    this.readSnapshot,
    this.interval = kLivePollingInterval,
    this.minimumQuietGap = const Duration(seconds: 2),
  });

  /// Ref Riverpod (pour pouvoir read le provider courant).
  final WidgetRef ref;

  /// Callback qui declenche le fetch reseau. Typiquement
  /// `ref.read(myProvider.notifier).refresh()`.
  final Future<void> Function() refresh;

  /// Deprecie : la dedup est faite cote notifier. Conserve pour compat des
  /// call sites existants ; ignore.
  final Object? Function()? readSnapshot;

  /// Periode entre 2 ticks. Defaut 30 s.
  final Duration interval;

  /// Si l'utilisateur a fait un pull-to-refresh il y a moins de ce delai,
  /// on saute le prochain tick auto pour ne pas dupliquer.
  final Duration minimumQuietGap;

  Timer? _timer;
  DateTime? _lastTickAt;
  bool _running = false;

  bool get isRunning => _running;

  /// Demarre le polling. Idempotent : un second appel n'a aucun effet.
  void start() {
    if (_running) return;
    _running = true;
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

  /// Reconnait que l'utilisateur vient de faire un pull-to-refresh manuel :
  /// reset le timer pour eviter un double fetch immediat.
  void notifyManualRefresh() {
    _lastTickAt = DateTime.now();
  }

  Future<void> _tick() async {
    final last = _lastTickAt;
    if (last != null && DateTime.now().difference(last) < minimumQuietGap) {
      // L'utilisateur vient de faire pull-to-refresh; on saute ce tick auto.
      return;
    }
    _lastTickAt = DateTime.now();
    // La dedup + le "garde la donnee sur echec" sont geres par le notifier.
    await refresh();
  }
}
