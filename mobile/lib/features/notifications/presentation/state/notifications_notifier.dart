import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/services/local_notif_service.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/app_notification.dart';

class NotificationsNotifier extends AsyncNotifier<List<AppNotification>> {
  late final _list = ref.read(listNotificationsUseCaseProvider);
  late final _markRead = ref.read(markNotificationReadUseCaseProvider);
  late final _markAllRead = ref.read(markAllNotificationsReadUseCaseProvider);

  /// IDs des notifications backend deja vues lors du build initial . on
  /// n'affiche PAS de push local pour ces dernieres (elles existaient deja).
  /// Le set se peuple au premier build et ne grossit qu'apres . on push
  /// uniquement pour les IDs qui n'y figurent pas encore.
  final Set<int> _seenIds = <int>{};

  @override
  Future<List<AppNotification>> build() async {
    final items = await _list.call(const NoParams());
    // Premier chargement : on enregistre les IDs sans pousser de notif locale.
    for (final n in items) {
      _seenIds.add(n.id);
    }
    return items;
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final items = await _list.call(const NoParams());
      await _maybePushNew(items);
      return items;
    });
  }

  /// Affiche une push locale pour chaque notif backend dont l'ID n'a pas
  /// encore ete vu. Best-effort . echec d'affichage n'interrompt pas le
  /// refresh.
  Future<void> _maybePushNew(List<AppNotification> items) async {
    for (final n in items) {
      if (_seenIds.contains(n.id)) continue;
      _seenIds.add(n.id);
      try {
        await LocalNotifService.instance.showInstant(
          id: n.id,
          title: n.title,
          body: n.body,
          payload: 'notif:${n.id}',
        );
      } catch (_) {
        // Pas critique . la notif reste visible dans la page in-app.
      }
    }
  }

  Future<void> markRead(int id) async {
    await _markRead.call(id);
    // Refresh local list (the data source is the source of truth pour le mock).
    state = await AsyncValue.guard(() => _list.call(const NoParams()));
  }

  Future<void> markAllRead() async {
    await _markAllRead.call(const NoParams());
    state = await AsyncValue.guard(() => _list.call(const NoParams()));
  }
}

final notificationsProvider = AsyncNotifierProvider<NotificationsNotifier,
    List<AppNotification>>(NotificationsNotifier.new);

/// Compteur dérivé du nombre de notifications non lues . utilisé dans la
/// cloche du header.
final unreadNotifsCountProvider = Provider<int>((ref) {
  final notifs = ref.watch(notificationsProvider);
  return notifs.maybeWhen(
    data: (items) => items.where((n) => !n.read).length,
    orElse: () => 0,
  );
});
