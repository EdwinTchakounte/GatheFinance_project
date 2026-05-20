import '../entities/app_notification.dart';

abstract class NotificationsRepository {
  Future<List<AppNotification>> list();

  /// Marque toutes les notifications comme lues.
  Future<void> markAllRead();

  /// Marque une notification précise comme lue.
  Future<void> markRead(int id);
}
