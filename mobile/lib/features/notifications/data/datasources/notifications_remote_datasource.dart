import '../../domain/entities/app_notification.dart';

abstract class NotificationsRemoteDataSource {
  Future<List<AppNotification>> list();
  Future<void> markAllRead();
  Future<void> markRead(int id);
}
