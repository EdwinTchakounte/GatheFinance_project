import '../../domain/entities/app_notification.dart';
import 'notifications_remote_datasource.dart';

class NotificationsMockDataSource implements NotificationsRemoteDataSource {
  NotificationsMockDataSource() {
    _seed();
  }

  late List<AppNotification> _items;

  void _seed() {
    final now = DateTime.now();
    _items = [
      AppNotification(
        id: 1,
        kind: NotifKind.savings,
        title: 'Dépôt confirmé',
        body:
            'Ton dépôt de 25 000 XAF a été crédité. Nouveau solde : 365 000 XAF.',
        createdAt: now.subtract(const Duration(hours: 6)),
      ),
      AppNotification(
        id: 2,
        kind: NotifKind.loan,
        title: 'Prochaine échéance',
        body: 'L\'échéance n°4 de 46 667 XAF arrive dans 7 jours.',
        createdAt: now.subtract(const Duration(days: 1)),
      ),
      AppNotification(
        id: 3,
        kind: NotifKind.payment,
        title: 'Frais de dossier reçus',
        body:
            'Tes frais de dossier de 5 000 XAF ont été reçus. Demande passe en instruction.',
        createdAt: now.subtract(const Duration(days: 2)),
        read: true,
      ),
      AppNotification(
        id: 4,
        kind: NotifKind.system,
        title: 'Bienvenue dans l\'app',
        body: 'Ton espace mobile Gathe Finance est désormais actif.',
        createdAt: now.subtract(const Duration(days: 4)),
        read: true,
      ),
    ];
  }

  AppNotification _withRead(AppNotification n) => AppNotification(
        id: n.id,
        kind: n.kind,
        title: n.title,
        body: n.body,
        createdAt: n.createdAt,
        read: true,
      );

  @override
  Future<List<AppNotification>> list() async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    return List.unmodifiable(_items);
  }

  @override
  Future<void> markRead(int id) async {
    await Future<void>.delayed(const Duration(milliseconds: 120));
    final idx = _items.indexWhere((n) => n.id == id);
    if (idx >= 0 && !_items[idx].read) {
      _items[idx] = _withRead(_items[idx]);
    }
  }

  @override
  Future<void> markAllRead() async {
    await Future<void>.delayed(const Duration(milliseconds: 180));
    _items = _items.map((n) => n.read ? n : _withRead(n)).toList();
  }
}
