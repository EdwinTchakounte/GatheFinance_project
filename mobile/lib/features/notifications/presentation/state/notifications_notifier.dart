import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../core/di/providers.dart';
import '../../../../core/usecases/usecase.dart';
import '../../domain/entities/app_notification.dart';

class NotificationsNotifier extends AsyncNotifier<List<AppNotification>> {
  late final _list = ref.read(listNotificationsUseCaseProvider);
  late final _markRead = ref.read(markNotificationReadUseCaseProvider);
  late final _markAllRead = ref.read(markAllNotificationsReadUseCaseProvider);

  @override
  Future<List<AppNotification>> build() => _list.call(const NoParams());

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => _list.call(const NoParams()));
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

/// Compteur dérivé du nombre de notifications non lues — utilisé dans la
/// cloche du header.
final unreadNotifsCountProvider = Provider<int>((ref) {
  final notifs = ref.watch(notificationsProvider);
  return notifs.maybeWhen(
    data: (items) => items.where((n) => !n.read).length,
    orElse: () => 0,
  );
});
