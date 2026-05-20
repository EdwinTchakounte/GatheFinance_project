import 'package:flutter_test/flutter_test.dart';
import 'package:gathe_finance/core/usecases/usecase.dart';
import 'package:gathe_finance/features/notifications/domain/repositories/notifications_repository.dart';
import 'package:gathe_finance/features/notifications/domain/usecases/list_notifications.dart';
import 'package:gathe_finance/features/notifications/domain/usecases/mark_notification_read.dart';
import 'package:mocktail/mocktail.dart';

import '../../../../helpers/fixtures.dart';

class _MockRepo extends Mock implements NotificationsRepository {}

void main() {
  late _MockRepo repo;

  setUp(() => repo = _MockRepo());

  test('ListNotifications délègue au repo', () async {
    final fixtures = Fixtures.notifications();
    when(() => repo.list()).thenAnswer((_) async => fixtures);
    final result =
        await ListNotifications(repo).call(const NoParams());
    expect(result.length, fixtures.length);
  });

  test('MarkNotificationRead transmet l\'id', () async {
    when(() => repo.markRead(42)).thenAnswer((_) async {});
    await MarkNotificationRead(repo).call(42);
    verify(() => repo.markRead(42)).called(1);
  });

  test('MarkAllNotificationsRead n\'a pas de paramètres', () async {
    when(() => repo.markAllRead()).thenAnswer((_) async {});
    await MarkAllNotificationsRead(repo).call(const NoParams());
    verify(() => repo.markAllRead()).called(1);
  });
}
