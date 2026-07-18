import '../../domain/entities/app_notification.dart';

abstract class NotificationsRemoteDataSource {
  Future<List<AppNotification>> list();
  Future<void> markAllRead();
  Future<void> markRead(int id);
  Future<void> registerDevice(String token, {String platform});
  Future<void> unregisterDevice(String token);

  /// Préférences push par catégorie (opt-out) : `{categorie: bool}`.
  Future<Map<String, bool>> getPushPrefs();

  /// Fusionne une mise à jour partielle et renvoie la map complète.
  Future<Map<String, bool>> setPushPrefs(Map<String, bool> updates);
}
