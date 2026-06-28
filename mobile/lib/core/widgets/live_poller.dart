import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../utils/live_polling.dart';

/// Widget sentinelle a poser dans la tree d'une page : declenche un fetch
/// reseau toutes les [interval] secondes via [refresh], et arrete le timer
/// quand la page est unmount.
///
/// Ne rend rien (SizedBox.shrink). A glisser au tout debut du body de la
/// page :
/// ```dart
/// Column(children: [
///   LivePoller(
///     refresh: () => ref.read(loansProvider.notifier).refresh(),
///     readSnapshot: () => ref.read(loansProvider).valueOrNull,
///   ),
///   // ... reste du body
/// ])
/// ```
///
/// Idempotence : la valeur retournee par [readSnapshot] est hashee en JSON
/// et comparee au tick precedent ; si identique, aucun rebuild n'est
/// declenche (cf. [LivePolling]).
///
/// Bonus : si tu fais un pull-to-refresh manuel, appelle [.of(context)]
/// `.notifyManualRefresh()` pour eviter un double fetch au prochain tick.
class LivePoller extends ConsumerStatefulWidget {
  const LivePoller({
    super.key,
    required this.refresh,
    required this.readSnapshot,
    this.interval = kLivePollingInterval,
  });

  final Future<void> Function() refresh;
  final Object? Function() readSnapshot;
  final Duration interval;

  @override
  ConsumerState<LivePoller> createState() => _LivePollerState();
}

class _LivePollerState extends ConsumerState<LivePoller> {
  LivePolling? _polling;

  @override
  void initState() {
    super.initState();
    _polling = LivePolling(
      ref: ref,
      refresh: widget.refresh,
      readSnapshot: widget.readSnapshot,
      interval: widget.interval,
    );
    _polling!.start();
  }

  @override
  void dispose() {
    _polling?.stop();
    _polling = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
