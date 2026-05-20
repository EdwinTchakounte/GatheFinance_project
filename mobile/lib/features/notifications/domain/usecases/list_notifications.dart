import '../../../../core/usecases/usecase.dart';
import '../entities/app_notification.dart';
import '../repositories/notifications_repository.dart';

class ListNotifications extends UseCase<List<AppNotification>, NoParams> {
  const ListNotifications(this._repo);
  final NotificationsRepository _repo;

  @override
  Future<List<AppNotification>> call(NoParams params) => _repo.list();
}
