import '../../../../core/usecases/usecase.dart';
import '../repositories/notifications_repository.dart';

class MarkNotificationRead extends UseCase<void, int> {
  const MarkNotificationRead(this._repo);
  final NotificationsRepository _repo;

  @override
  Future<void> call(int id) => _repo.markRead(id);
}

class MarkAllNotificationsRead extends UseCase<void, NoParams> {
  const MarkAllNotificationsRead(this._repo);
  final NotificationsRepository _repo;

  @override
  Future<void> call(NoParams params) => _repo.markAllRead();
}
