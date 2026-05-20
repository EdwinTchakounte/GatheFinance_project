import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/notification_prefs.dart';

/// Notifier des préférences de notifications, persistées via
/// SharedPreferences. Chaque combo (cat, chan) est stocké sous la clé
/// `notif_pref_<cat>_<chan>` en bool.
class NotificationPrefsNotifier extends AsyncNotifier<NotificationPrefs> {
  static String _key(NotifCategory cat, NotifChannel chan) =>
      'notif_pref_${cat.name}_${chan.name}';

  @override
  Future<NotificationPrefs> build() async {
    final prefs = await SharedPreferences.getInstance();
    final defaults = NotificationPrefs.defaults();
    final matrix = {
      for (final cat in NotifCategory.values)
        cat: {
          for (final chan in NotifChannel.values)
            chan: prefs.getBool(_key(cat, chan)) ??
                defaults.isEnabled(cat, chan),
        },
    };
    return NotificationPrefs(matrix);
  }

  Future<void> toggle(NotifCategory cat, NotifChannel chan, bool value) async {
    final current = state.valueOrNull ?? NotificationPrefs.defaults();
    state = AsyncValue.data(current.setEnabled(cat, chan, value));
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key(cat, chan), value);
  }
}

final notificationPrefsProvider =
    AsyncNotifierProvider<NotificationPrefsNotifier, NotificationPrefs>(
  NotificationPrefsNotifier.new,
);
