import '../entities/app_notification.dart';

abstract class NotificationsRepository {
  Future<List<AppNotification>> list();

  /// Marque toutes les notifications comme lues.
  Future<void> markAllRead();

  /// Marque une notification précise comme lue.
  Future<void> markRead(int id);

  /// Enregistre le jeton push de l'appareil (bases FCM/APNs).
  Future<void> registerDevice(String token, {String platform});

  /// Désenregistre un jeton push (logout / rotation).
  Future<void> unregisterDevice(String token);

  /// Préférences push par catégorie (opt-out) : `{categorie: bool}`.
  Future<Map<String, bool>> getPushPrefs();

  /// Fusionne une mise à jour partielle et renvoie la map complète.
  Future<Map<String, bool>> setPushPrefs(Map<String, bool> updates);
}
