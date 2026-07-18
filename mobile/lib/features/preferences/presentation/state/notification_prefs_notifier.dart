import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../../core/di/providers.dart';
import '../../domain/notification_prefs.dart';

/// Notifier des préférences de notification **push** par catégorie.
///
/// Source de vérité = backend (`/notifications/preferences/`).
/// SharedPreferences (clé `notif_push_<cat>`) sert de **cache** pour un
/// affichage instantané et un repli hors-ligne.
class NotificationPrefsNotifier extends AsyncNotifier<NotificationPrefs> {
  static String _key(NotifCategory cat) => 'notif_push_${cat.name}';

  @override
  Future<NotificationPrefs> build() async {
    final prefs = await SharedPreferences.getInstance();
    final cached = NotificationPrefs({
      for (final c in NotifCategory.values) c: prefs.getBool(_key(c)) ?? true,
    });
    try {
      final remote =
          await ref.read(notificationsRepositoryProvider).getPushPrefs();
      final result = NotificationPrefs.fromApi(remote);
      await _cache(prefs, result);
      return result;
    } catch (_) {
      return cached; // hors-ligne / erreur : on garde le cache local
    }
  }

  Future<void> toggle(NotifCategory cat, bool value) async {
    final current = state.valueOrNull ?? NotificationPrefs.defaults();
    state = AsyncValue.data(current.setEnabled(cat, value)); // optimiste
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key(cat), value);
    try {
      final remote = await ref
          .read(notificationsRepositoryProvider)
          .setPushPrefs({cat.name: value});
      final synced = NotificationPrefs.fromApi(remote);
      state = AsyncValue.data(synced);
      await _cache(prefs, synced);
    } catch (_) {
      // On conserve l'état optimiste + cache ; resync au prochain build().
    }
  }

  Future<void> _cache(SharedPreferences prefs, NotificationPrefs p) async {
    for (final entry in p.push.entries) {
      await prefs.setBool(_key(entry.key), entry.value);
    }
  }
}

final notificationPrefsProvider =
    AsyncNotifierProvider<NotificationPrefsNotifier, NotificationPrefs>(
  NotificationPrefsNotifier.new,
);
