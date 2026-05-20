import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/di/providers.dart';
import 'package:gathe_finance/features/notifications/data/datasources/notifications_remote_datasource.dart';
import 'package:gathe_finance/features/notifications/domain/entities/app_notification.dart';
import 'package:gathe_finance/features/notifications/presentation/pages/notifications_page.dart';

/// Datasource paramétrable pour les tests notifications.
class _ScriptedNotifsDs implements NotificationsRemoteDataSource {
  _ScriptedNotifsDs(this._items);
  List<AppNotification> _items;
  int markAllCalls = 0;
  final List<int> markedIds = [];

  @override
  Future<List<AppNotification>> list() async => List.unmodifiable(_items);

  @override
  Future<void> markAllRead() async {
    markAllCalls += 1;
    _items = _items
        .map((n) => AppNotification(
              id: n.id,
              kind: n.kind,
              title: n.title,
              body: n.body,
              createdAt: n.createdAt,
              read: true,
            ))
        .toList();
  }

  @override
  Future<void> markRead(int id) async {
    markedIds.add(id);
    _items = _items
        .map((n) => n.id == id
            ? AppNotification(
                id: n.id,
                kind: n.kind,
                title: n.title,
                body: n.body,
                createdAt: n.createdAt,
                read: true,
              )
            : n)
        .toList();
  }
}

void main() {
  Widget app(Widget child, _ScriptedNotifsDs ds) {
    return ProviderScope(
      overrides: [notificationsDataSourceProvider.overrideWithValue(ds)],
      child: MaterialApp(home: child),
    );
  }

  testWidgets('NotificationsPage — empty state affiché si la liste est vide',
      (tester) async {
    final ds = _ScriptedNotifsDs([]);
    await tester.pumpWidget(app(const NotificationsPage(), ds));
    await tester.pumpAndSettle();

    expect(find.text('Aucune notification'), findsOneWidget);
    expect(find.byIcon(Icons.notifications_off_outlined), findsOneWidget);
  });

  testWidgets('NotificationsPage — affiche les items et le bouton Tout lire',
      (tester) async {
    final ds = _ScriptedNotifsDs([
      AppNotification(
        id: 1,
        kind: NotifKind.savings,
        title: 'Dépôt confirmé',
        body: 'Détail dépôt',
        createdAt: DateTime.now().subtract(const Duration(hours: 2)),
      ),
      AppNotification(
        id: 2,
        kind: NotifKind.loan,
        title: 'Échéance bientôt',
        body: 'Détail échéance',
        createdAt: DateTime.now().subtract(const Duration(days: 1)),
      ),
    ]);
    await tester.pumpWidget(app(const NotificationsPage(), ds));
    await tester.pumpAndSettle();

    expect(find.text('Dépôt confirmé'), findsOneWidget);
    expect(find.text('Échéance bientôt'), findsOneWidget);
    expect(find.text('Tout lire'), findsOneWidget);
  });

  testWidgets('NotificationsPage — Tout lire appelle markAllRead',
      (tester) async {
    final ds = _ScriptedNotifsDs([
      AppNotification(
        id: 1,
        kind: NotifKind.savings,
        title: 'Test',
        body: 'Test body',
        createdAt: DateTime.now(),
      ),
    ]);
    await tester.pumpWidget(app(const NotificationsPage(), ds));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Tout lire'));
    await tester.pumpAndSettle();

    expect(ds.markAllCalls, 1);
  });
}
