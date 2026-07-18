import '../../../../core/error/exceptions.dart';
import '../../../../core/error/failures.dart';
import '../../domain/entities/app_notification.dart';
import '../../domain/repositories/notifications_repository.dart';
import '../datasources/notifications_remote_datasource.dart';

class NotificationsRepositoryImpl implements NotificationsRepository {
  const NotificationsRepositoryImpl(this._remote);
  final NotificationsRemoteDataSource _remote;

  Future<T> _run<T>(Future<T> Function() op) async {
    try {
      return await op();
    } on NetworkException catch (e) {
      throw NetworkFailure(e.message);
    } on ServerException catch (e) {
      throw UnexpectedFailure(e.message);
    }
  }

  @override
  Future<List<AppNotification>> list() => _run(_remote.list);

  @override
  Future<void> markRead(int id) => _run(() => _remote.markRead(id));

  @override
  Future<void> markAllRead() => _run(_remote.markAllRead);

  @override
  Future<void> registerDevice(String token, {String platform = 'android'}) =>
      _run(() => _remote.registerDevice(token, platform: platform));

  @override
  Future<void> unregisterDevice(String token) =>
      _run(() => _remote.unregisterDevice(token));

  @override
  Future<Map<String, bool>> getPushPrefs() => _run(_remote.getPushPrefs);

  @override
  Future<Map<String, bool>> setPushPrefs(Map<String, bool> updates) =>
      _run(() => _remote.setPushPrefs(updates));
}
